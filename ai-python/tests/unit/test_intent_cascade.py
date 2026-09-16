from app.intent import cascade
from app.intent.classifier import LightweightIntentClassifier, LightweightPrediction
from app.intent.rules import detect_safety_flags, match_rules, normalize_text


def test_normalize_text_handles_full_width_and_spaces():
    assert normalize_text("  ＨＥＬＬＯ　World  ") == "hello world"


def test_rules_route_exact_social_without_model():
    result = match_rules("谢谢你啊！")

    assert result is not None
    assert result.selected_agents == ["chat"]
    assert result.matched_rules == ["exact_social"]


def test_rules_route_identity_question_as_chat():
    result = match_rules("你是谁？")

    assert result is not None
    assert result.selected_agents == ["chat"]
    assert result.matched_rules == ["exact_identity"]


def test_rules_route_common_identity_variants_as_chat():
    for text in ("你是谁", "你叫什么名字", "你能做什么", "介绍一下你自己"):
        result = match_rules(text)
        assert result is not None, text
        assert result.selected_agents == ["chat"], text
        assert result.matched_rules == ["exact_identity"], text


def test_rules_route_symptom_list_question_as_knowledge():
    result = match_rules("感冒有哪些症状？")

    assert result is not None
    assert result.selected_agents == ["knowledge"]
    assert result.matched_rules == ["explicit_medical_question"]


def test_rules_keep_web_search_request_on_medical_path():
    result = match_rules("联网搜索一下感冒的症状")

    assert result is not None
    assert result.selected_agents == ["knowledge"]
    assert "explicit_medical_question" in result.matched_rules


def test_rules_route_current_clock_question_as_chat():
    result = match_rules("几点了")

    assert result is not None
    assert result.selected_agents == ["chat"]
    assert result.matched_rules == ["exact_clock_question"]


def test_rules_route_colloquial_clock_and_date_questions_as_chat():
    for text in ("现在几点", "现在几点了啊", "请问现在几点了", "今天几号", "今天星期几"):
        result = match_rules(text)
        assert result is not None, text
        assert result.selected_agents == ["chat"], text
        assert result.matched_rules == ["exact_clock_question"], text


def test_rules_do_not_treat_appointment_or_hours_as_clock_question():
    assert match_rules("几点有号") is None
    assert match_rules("几点能挂号") is None
    hours = match_rules("诊所几点开门")
    assert hours is not None
    assert hours.matched_rules == ["hospital_static_information"]


def test_rules_do_not_treat_generic_location_question_as_hospital_static():
    assert match_rules("心脏在人体的哪里") is None


def test_rules_do_not_treat_hanging_a_picture_as_registration():
    assert match_rules("帮我挂在墙上的这幅画") is None


def test_rules_recognize_colloquial_registration_without_the_word_hao():
    result = match_rules("请给我挂明天的内科")

    assert result is not None
    assert result.selected_agents == ["tools"]


def test_rules_keep_identity_when_mixed_with_medical_and_business():
    result = match_rules(
        "你是谁？能干什么？联网告诉我感冒会的症状。此外帮我看明天有哪些号源？"
        "如果有骨科号源那就挂下午的骨科如果没有那就挂儿科"
    )

    assert result is not None
    assert set(result.selected_agents) == {"chat", "knowledge", "tools"}
    assert "identity_with_other_intents" in result.matched_rules


def test_rules_combine_medical_and_business_intents():
    result = match_rules("孩子发烧怎么办，帮我挂明天儿科")

    assert result is not None
    assert result.selected_agents == ["tools", "knowledge"]
    assert "appointment_action" in result.matched_rules
    assert "explicit_medical_question" in result.matched_rules


def test_safety_rule_is_orthogonal_to_appointment_intent():
    result = match_rules("突然胸痛而且喘不上气，帮我挂号")

    assert result is not None
    assert result.selected_agents == ["knowledge", "tools"]
    assert result.safety_flags == ["breathing_difficulty", "acute_chest_pain"]


def test_lightweight_classifier_accepts_close_domain_query():
    classifier = LightweightIntentClassifier()

    result = classifier.predict("胃不舒服应该怎么处理")

    assert result.accepted is True
    assert result.selected_agents == ["knowledge"]
    assert result.scores["knowledge"] >= classifier.acceptance_threshold


def test_lightweight_classifier_rejects_out_of_distribution_query():
    classifier = LightweightIntentClassifier()

    result = classifier.predict("解释一下量子纠缠和黑洞信息悖论")

    assert result.accepted is False
    assert result.reason in {"out_of_distribution", "low_confidence"}


class _StubClassifier:
    def __init__(self, prediction):
        self.prediction = prediction
        self.version = "test-model-v1"

    def predict(self, text):
        return self.prediction


def test_cascade_uses_lightweight_model_when_confident(monkeypatch):
    prediction = LightweightPrediction(
        selected_agents=["tools"],
        scores={"knowledge": 0.05, "chat": 0.05, "tools": 0.9},
        accepted=True,
        margin=0.85,
        nearest_similarity=0.8,
    )
    monkeypatch.setattr(cascade, "get_lightweight_classifier", lambda: _StubClassifier(prediction))

    result = cascade.route_locally("我想找一位医生")

    assert result.accepted is True
    assert result.stage == "lightweight_model"
    assert result.selected_agents == ["tools"]


def test_cascade_escalates_ambiguous_prediction(monkeypatch):
    prediction = LightweightPrediction(
        selected_agents=["knowledge"],
        scores={"knowledge": 0.61, "chat": 0.58, "tools": 0.1},
        accepted=False,
        margin=0.03,
        nearest_similarity=0.5,
        reason="ambiguous_top_intents",
    )
    monkeypatch.setattr(cascade, "get_lightweight_classifier", lambda: _StubClassifier(prediction))

    result = cascade.route_locally("这件事该怎么办")

    assert result.accepted is False
    assert result.stage == "llm_required"
    assert result.escalation_reason == "ambiguous_top_intents"
    assert result.selected_agents == ["knowledge"]


def test_detect_safety_flags_does_not_match_plain_chest_discomfort_as_acute():
    assert detect_safety_flags("胸口偶尔有一点不舒服") == []
