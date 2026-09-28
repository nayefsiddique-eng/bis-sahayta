import pytest
from app.services.intent_classifier import classify_intent, Intent

def test_general_qa_intent():
    assert classify_intent("What is BIS and what does it stand for?") == Intent.GENERAL_QA
    assert classify_intent("Give me an overview about BIS background") == Intent.GENERAL_QA
    assert classify_intent("Who is the head of Bureau of Indian Standards?") == Intent.GENERAL_QA

def test_compliance_check_intent():
    assert classify_intent("Does QCO mandatory apply to imported toys?") == Intent.COMPLIANCE_CHECK
    assert classify_intent("Is IS 9873 mandatory for wooden toys under BIS?") == Intent.COMPLIANCE_CHECK
    assert classify_intent("Are MSME exempted from footwear standard compliance?") == Intent.COMPLIANCE_CHECK

def test_certification_process_intent():
    assert classify_intent("What is the application procedure for ISI mark?") == Intent.CERTIFICATION_PROCESS
    assert classify_intent("Show me the steps and roadmap for factory audit") == Intent.CERTIFICATION_PROCESS
    assert classify_intent("How to get Manakonline license approval?") == Intent.CERTIFICATION_PROCESS

def test_hybrid_intent():
    assert classify_intent("Does QCO apply to toys and what is the process to get license?") == Intent.HYBRID
    assert classify_intent("Is IS 17043 mandatory for MSME and how to get application steps?") == Intent.HYBRID
    assert classify_intent("What is BIS and does QCO apply for solar modules?") == Intent.HYBRID
