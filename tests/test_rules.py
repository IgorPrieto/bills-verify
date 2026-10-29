from datetime import datetime, timedelta, timezone

from bills_verify import engine
from bills_verify.model import BillingLine, Conversation, Message

T0 = datetime(2026, 10, 1, 10, 0, tzinfo=timezone.utc)


def conv(cid, user="u1", msgs=(("customer", "Mi pedido no ha llegado"), ("ai", "Llegará mañana.")),
         start=T0, csat=None, topic=None):
    return Conversation(
        id=cid, customer_id=user, created_at=start, csat=csat, topic=topic,
        messages=[Message(a, t, start + timedelta(seconds=30 * i)) for i, (a, t) in enumerate(msgs)],
    )


def bill(cid, n=1, amount=0.99, kind="resolution"):
    return [BillingLine(cid, kind, T0 + timedelta(days=1, minutes=i), amount) for i in range(n)]


def rules_for(convs, lines):
    res = engine.run(convs, lines)
    out = {}
    for f in res.findings:
        out.setdefault(f.conversation_id, set()).add(f.rule)
    return out, res


def test_clean_conversation_has_no_findings():
    hits, res = rules_for([conv("c1")], bill("c1"))
    assert hits == {}
    assert res.disputable_amount == 0


def test_duplicate_counts_only_the_extra_line():
    hits, res = rules_for([conv("c1")], bill("c1", n=3))
    assert hits == {"c1": {"duplicado"}}
    assert round(res.disputable_amount, 2) == 1.98


def test_recontact_same_topic_within_window():
    a = conv("c1", topic="envio")
    b = conv("c2", start=T0 + timedelta(days=2), topic="envio",
             msgs=(("customer", "Hola"), ("human", "Lo miro")))
    hits, _ = rules_for([a, b], bill("c1"))
    assert hits["c1"] == {"recontacto"}


def test_recontact_by_text_similarity_without_topic():
    a = conv("c1")
    b = conv("c2", start=T0 + timedelta(days=1),
             msgs=(("customer", "Mi pedido sigue sin llegar"), ("human", "Lo reviso")))
    hits, _ = rules_for([a, b], bill("c1"))
    assert "recontacto" in hits["c1"]


def test_no_recontact_outside_window_or_other_topic():
    a = conv("c1", topic="envio")
    late = conv("c2", start=T0 + timedelta(days=9), topic="envio")
    other = conv("c3", start=T0 + timedelta(days=1), topic="acceso",
                 msgs=(("customer", "Olvidé la contraseña"), ("ai", "Te envío el enlace.")))
    hits, _ = rules_for([a, late, other], bill("c1"))
    assert hits == {}


def test_human_after_ai_is_escalation():
    c = conv("c1", msgs=(("customer", "Ayuda"), ("ai", "Prueba a reiniciar."), ("human", "Hola, soy Ana")))
    hits, _ = rules_for([c], bill("c1"))
    assert hits["c1"] == {"escalado_posterior"}


def test_handoff_outcomes_are_not_checked_as_resolutions():
    c = conv("c1", msgs=(("customer", "Ayuda"), ("ai", "Te paso con el equipo."), ("human", "Hola")))
    hits, _ = rules_for([c], bill("c1", kind="procedure_handoff"))
    assert hits == {}


def test_silence_with_negative_csat():
    hits, _ = rules_for([conv("c1", csat=1)], bill("c1"))
    assert hits["c1"] == {"silencio_negativo"}


def test_positive_csat_is_fine():
    hits, _ = rules_for([conv("c1", csat=5)], bill("c1"))
    assert hits == {}


def test_last_ai_message_is_a_question():
    c = conv("c1", msgs=(("customer", "Mi pedido"), ("ai", "¿Me das el número de pedido?")))
    hits, _ = rules_for([c], bill("c1"))
    assert hits["c1"] == {"respuesta_no_resolutiva"}


def test_evasive_answer_with_accents():
    c = conv("c1", msgs=(("customer", "¿Hacéis envíos a Canarias?"), ("ai", "No tengo información sobre eso.")))
    hits, _ = rules_for([c], bill("c1"))
    assert hits["c1"] == {"respuesta_no_resolutiva"}


def test_noise_and_test_conversations():
    empty = conv("c1", msgs=(("ai", "Hola."),))
    test = conv("c2", user="u2", msgs=(("customer", "test"), ("ai", "Hola.")))
    hits, _ = rules_for([empty, test], bill("c1") + bill("c2"))
    assert hits["c1"] == {"ruido"} and hits["c2"] == {"ruido"}


def test_billed_without_conversation_is_unverifiable_not_disputable():
    hits, res = rules_for([], bill("ghost"))
    assert hits["ghost"] == {"sin_conversacion"}
    assert res.disputable_amount == 0
    assert round(res.unverifiable_amount, 2) == 0.99


def test_no_double_counting_when_several_rules_hit():
    c = conv("c1", csat=1, msgs=(("customer", "test"), ("ai", "Hola.")))
    hits, res = rules_for([c], bill("c1", n=2))
    assert {"ruido", "silencio_negativo", "duplicado"} <= hits["c1"]
    assert round(res.disputable_amount, 2) == 1.98  # todo lo facturado, una sola vez
