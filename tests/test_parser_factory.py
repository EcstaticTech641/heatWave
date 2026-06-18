"""
Module: test_parser_factory.py
Purpose: Verify routing integrity of ParserFactory to ensure correct strategies are returned.
Inputs: Sample text from different formats (Hy-Tek, TeamUnify, Generic).
Outputs: Assertion outcomes.
Dependencies: pytest, src.parser.extractor
Architecture role: Integrity tests for the Strategy and Factory design.
"""
from pathlib import Path
from src.parser.extractor import (
    ParserFactory,
    HyTekParser,
    TeamUnifyParser,
    GenericParser,
)


def test_parser_routing():
    """Verify that ParserFactory.get_parser routes inputs to the correct strategy classes."""
    hytek_text = "Welcome to the meet\nHy-Tek's Meet Manager 8.0"
    teamunify_text = "Powered by TeamUnify database"
    generic_text = "Some random swimming document text"
    
    assert isinstance(ParserFactory.get_parser(hytek_text), HyTekParser)
    assert isinstance(ParserFactory.get_parser(teamunify_text), TeamUnifyParser)
    assert isinstance(ParserFactory.get_parser(generic_text), GenericParser)


def test_parser_routing_with_files():
    """Verify routing with actual sample files."""
    hytek_path = Path("data/test_suite/hytek_sample.txt")
    teamunify_path = Path("data/test_suite/teamunify_sample.txt")
    
    assert hytek_path.exists(), "Hy-Tek sample is missing"
    assert teamunify_path.exists(), "TeamUnify sample is missing"
    
    hytek_content = hytek_path.read_text(encoding="utf-8")
    teamunify_content = teamunify_path.read_text(encoding="utf-8")
    
    assert isinstance(ParserFactory.get_parser(hytek_content), HyTekParser)
    assert isinstance(ParserFactory.get_parser(teamunify_content), TeamUnifyParser)
