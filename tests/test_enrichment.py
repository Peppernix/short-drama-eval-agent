from drama_eval.enrichment import attach_evidence


def test_attach_evidence_by_time_and_label():
    manifest = {
        "shots": [
            {
                "shot_id": 1,
                "start": 0.0,
                "end": 3.0,
                "keyframes": [{"label": "original_shot_001_t1.00"}],
            },
            {
                "shot_id": 2,
                "start": 3.0,
                "end": 6.0,
                "keyframes": [{"label": "original_shot_002_t4.00"}],
            },
        ]
    }
    transcript = {
        "segments": [
            {"start": 0.2, "end": 1.5, "text": "你为什么骗我"},
            {"start": 3.2, "end": 5.0, "text": "事情不是这样的"},
        ]
    }
    ocr = {
        "frames": [
            {"label": "original_shot_002_t4.00", "texts": ["三年后"], "confidence": "high"}
        ]
    }

    attach_evidence(manifest, transcript, ocr)

    assert manifest["shots"][0]["asr_segments"][0]["text"] == "你为什么骗我"
    assert manifest["shots"][1]["asr_segments"][0]["text"] == "事情不是这样的"
    assert manifest["shots"][1]["keyframes"][0]["ocr_texts"] == ["三年后"]
    assert manifest["shots"][0]["keyframes"][0]["ocr_texts"] == []
