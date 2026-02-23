"""Tests for robots.txt handling."""
import sys
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from leadfinder.robots import RobotsChecker, _origin, _robots_url


def test_origin():
    assert _origin("https://example.com/path") == "https://example.com"
    assert _origin("http://sub.example.com:8080/page") == "http://sub.example.com:8080"


def test_robots_url():
    assert _robots_url("https://example.com") == "https://example.com/robots.txt"
    assert _robots_url("https://example.com/contact") == "https://example.com/robots.txt"


def test_robots_can_fetch_allow_all():
    """When robots.txt is missing or empty, allow all."""
    checker = RobotsChecker(user_agent="TestBot/1.0")
    mock_client = MagicMock()
    mock_client.get.return_value.status_code = 404
    mock_client.get.return_value.text = ""
    checker.fetch_robots("https://example.com/page", mock_client)
    # After 404 we parse [] which typically allows all in RobotFileParser
    can = checker.can_fetch("https://example.com/any", mock_client)
    assert can is True


def test_robots_caches_per_origin():
    checker = RobotsChecker(user_agent="TestBot/1.0")
    mock_client = MagicMock()
    mock_client.get.return_value.status_code = 200
    mock_client.get.return_value.text = "User-agent: *\nDisallow: /admin\n"
    checker.fetch_robots("https://example.com/", mock_client)
    assert "https://example.com" in checker._parsers
    can_admin = checker.can_fetch("https://example.com/admin", mock_client)
    can_contact = checker.can_fetch("https://example.com/contact", mock_client)
    assert can_admin is False
    assert can_contact is True
