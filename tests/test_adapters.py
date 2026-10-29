import json

from bills_verify import billing
from bills_verify.adapters import common, intercom, zendesk


def test_intercom_maps_authors_and_strips_html(tmp_path):
    data = {"conversations": [{
        "id": 1, "created_at": 1759312800,
        "source": {"body": "<p>Mi <b>pedido</b> no llega</p>", "author": {"type": "user", "id": "u9"}},
        "contacts": {"contacts": [{"id": "u9"}]},
        "conversation_rating": {"rating": 2},
        "tags": {"tags": [{"name": "envio"}]},
        "conversation_parts": {"conversation_parts": [
            {"part_type": "assignment", "body": None, "author": {"type": "admin"}, "created_at": 1759312810},
            {"part_type": "comment", "body": "<p>Llega mañana</p>", "author": {"type": "bot"}, "created_at": 1759312860},
            {"part_type": "comment", "body": "Hola, soy Ana", "author": {"type": "admin"}, "created_at": 1759312900},
        ]},
    }]}
    p = tmp_path / "ic.json"
    p.write_text(json.dumps(data))
    [c] = intercom.load(p)
    assert c.id == "1" and c.customer_id == "u9" and c.csat == 2 and c.topic == "envio"
    assert [m.author for m in c.messages] == ["customer", "ai", "human"]
    assert c.messages[0].text == "Mi pedido no llega"


def test_zendesk_jsonl_and_ai_author_mapping(tmp_path):
    t = {"id": 42, "requester_id": 1001, "created_at": "2026-10-01T10:00:00Z", "tags": ["facturacion"],
         "satisfaction_rating": {"score": "bad"},
         "comments": [
             {"author_id": 1001, "plain_body": "No llega la factura", "created_at": "2026-10-01T10:00:00Z"},
             {"author_id": 7, "plain_body": "Te la reenvío.", "created_at": "2026-10-01T10:00:30Z"},
             {"author_id": 8, "plain_body": "Soy Luis", "created_at": "2026-10-01T10:05:00Z"},
         ]}
    p = tmp_path / "zd.jsonl"
    p.write_text(json.dumps(t) + "\n")
    [c] = zendesk.load(p, ai_author_ids=["7"])
    assert [m.author for m in c.messages] == ["customer", "ai", "human"]
    assert c.csat == 1 and c.topic == "facturacion"


def test_common_format_roundtrip(tmp_path):
    p = tmp_path / "c.json"
    p.write_text(json.dumps({"conversations": [{
        "id": "a", "customer_id": "u", "created_at": "2026-10-01T10:00:00Z",
        "messages": [{"author": "ai", "text": "B", "at": "2026-10-01T10:01:00Z"},
                     {"author": "customer", "text": "A", "at": "2026-10-01T10:00:00Z"}]}]}))
    [c] = common.load(p)
    assert [m.text for m in c.messages] == ["A", "B"]  # ordenados por tiempo


def test_billing_requires_columns(tmp_path):
    p = tmp_path / "b.csv"
    p.write_text("conversation_id,amount\nx,1\n")
    try:
        billing.load(p)
    except ValueError as e:
        assert "outcome_type" in str(e)
    else:
        raise AssertionError("debería fallar")
