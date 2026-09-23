from app.graphs.hospital.clinical_need import clinical_request


def test_general_knowledge_does_not_request_a_record():
    request = clinical_request(None, "高血压是什么？")

    assert request.scopes == ()
    assert request.needs_personal_records is False


def test_own_blood_pressure_requests_only_related_scopes():
    request = clinical_request(None, "我这个血压正常吗？")

    assert request.scopes == ("demographics", "blood_pressure", "past_history")
    assert request.medication_gap is False
    assert request.report_selection_required is False


def test_medication_question_records_missing_structures_as_gaps():
    request = clinical_request(None, "我能吃布洛芬吗？")

    assert "allergies" in request.scopes
    assert "past_history" in request.scopes
    assert "demographics" in request.scopes
    assert request.medication_gap is True


def test_report_question_lists_catalog_instead_of_opening_files():
    request = clinical_request(None, "帮我看看刚上传的报告")

    assert request.scopes == ("document_catalog",)
    assert request.report_selection_required is True


def test_cold_medicine_question_stays_general_even_with_first_person():
    request = clinical_request(None, "你好，我最近心情很难受所以感冒吃什么药")

    assert request.scopes == ()
