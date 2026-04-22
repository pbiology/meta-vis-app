# tests/unit/test_cases_serialise_ticket.py

from bson import ObjectId

from app.config import settings
from app.routers.cases import _serialise_case


def make_doc(ticket_id=None):
    doc = {
        "_id": ObjectId(),
        "case_id": "testcase",
        "sample_ids": [],
    }
    if ticket_id is not None:
        doc["ticket_id"] = ticket_id
    return doc


class TestSerialiseCaseTicketUrl:
    def test_no_ticket_id_no_ticket_url(self):
        result = _serialise_case(make_doc(ticket_id=None))
        assert "ticket_url" not in result

    def test_with_ticket_id_derives_url(self, monkeypatch):
        monkeypatch.setattr(
            settings,
            "freshdesk_base_url",
            "https://scilifelab.freshdesk.com/a/tickets/{ticket_id}",
        )
        result = _serialise_case(make_doc(ticket_id="12345"))
        assert result["ticket_id"] == "12345"
        assert (
            result["ticket_url"] == "https://scilifelab.freshdesk.com/a/tickets/12345"
        )

    def test_ticket_id_without_base_url_omits_url(self, monkeypatch):
        monkeypatch.setattr(settings, "freshdesk_base_url", None)
        result = _serialise_case(make_doc(ticket_id="12345"))
        assert result["ticket_id"] == "12345"
        assert "ticket_url" not in result
