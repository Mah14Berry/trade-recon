import json

from recon.explainer import explain_breaks, parse_response, strip_fences
from recon.matcher import QUANTITY_MISMATCH, parse_trades, reconcile

HEADER = "trade_id,ticker,quantity,price,trade_date,settle_date\n"


class Block:
    type = "text"

    def __init__(self, text):
        self.text = text


class Response:
    def __init__(self, text):
        self.content = [Block(text)]


class Messages:
    def __init__(self, text=None, error=None):
        self.text = text
        self.error = error
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return Response(self.text)


class Client:
    def __init__(self, text=None, error=None):
        self.messages = Messages(text, error)


def make_breaks():
    ledger = parse_trades(HEADER + "T1,AAPL,100,190.00,2026-09-01,2026-09-02\n", "ledger")
    custodian = parse_trades(HEADER + "T1,AAPL,90,190.00,2026-09-01,2026-09-02\n", "custodian")
    return reconcile(ledger, custodian).breaks


def reply(trade_id="T1"):
    return json.dumps([{"trade_id": trade_id, "explanation": "Ten shares short.", "suggested_action": "Call the broker."}])


def test_empty_breaks_return_none():
    assert explain_breaks([]) == "none"


def test_without_key_uses_rule_based_text():
    breaks = make_breaks()
    assert explain_breaks(breaks) == "rule_based"
    assert "10 shares" in breaks[0].explanation
    assert breaks[0].explained_by == "rules"


def test_llm_text_replaces_template():
    breaks = make_breaks()
    client = Client(reply())
    assert explain_breaks(breaks, client=client) == "llm"
    assert breaks[0].explanation == "Ten shares short."
    assert breaks[0].suggested_action == "Call the broker."
    assert breaks[0].explained_by == "llm"


def test_llm_never_changes_classification():
    breaks = make_breaks()
    explain_breaks(breaks, client=Client(reply()))
    assert breaks[0].break_type == QUANTITY_MISMATCH
    assert breaks[0].differences["quantity"] == {"ledger": "100", "custodian": "90"}


def test_fenced_json_is_accepted():
    breaks = make_breaks()
    explain_breaks(breaks, client=Client("```json\n" + reply() + "\n```"))
    assert breaks[0].explained_by == "llm"


def test_malformed_json_falls_back():
    breaks = make_breaks()
    assert explain_breaks(breaks, client=Client("sorry, no")) == "rule_based"
    assert breaks[0].explained_by == "rules"


def test_unknown_trade_ids_are_ignored():
    breaks = make_breaks()
    assert explain_breaks(breaks, client=Client(reply("T999"))) == "rule_based"


def test_api_error_falls_back():
    breaks = make_breaks()
    assert explain_breaks(breaks, client=Client(error=RuntimeError("down"))) == "rule_based"
    assert breaks[0].explanation


def test_request_sends_fixed_system_prompt_and_model():
    breaks = make_breaks()
    client = Client(reply())
    explain_breaks(breaks, client=client, model="test-model")
    call = client.messages.calls[0]
    assert call["model"] == "test-model"
    assert "never change it" in call["system"]
    assert json.loads(call["messages"][0]["content"])[0]["trade_id"] == "T1"


def test_parse_response_rejects_wrong_shapes():
    assert parse_response('{"trade_id": "T1"}', {"T1"}) == {}
    assert parse_response('["x"]', {"T1"}) == {}
    assert parse_response('[{"trade_id": "T1", "explanation": 5, "suggested_action": "a"}]', {"T1"}) == {}


def test_parse_response_truncates_long_text():
    long_text = "x" * 1000
    data = json.dumps([{"trade_id": "T1", "explanation": long_text, "suggested_action": "a"}])
    assert len(parse_response(data, {"T1"})["T1"][0]) == 300


def test_strip_fences_leaves_plain_text_alone():
    assert strip_fences("[1]") == "[1]"
