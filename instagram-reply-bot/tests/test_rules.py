"""Tests for ManyChat-style keyword rules and reply planning."""
from instagram_reply_bot.api import Comment
from instagram_reply_bot.config import Config
from instagram_reply_bot.rules import Rule, load_rules, plan_reply


def _comment(text, username="ana"):
    return Comment(id="c1", text=text, username=username, timestamp="t")


def _cfg(**overrides):
    cfg = Config.load()
    cfg.settings.update(overrides)
    return cfg


PRICING = {
    "name": "pricing",
    "keywords": ["price", "preço"],
    "reply": "Sent prices to @{name}!",
    "dm": "Prices: R$120",
}


def test_rule_substring_match():
    rule = Rule.from_dict(PRICING)
    assert rule.matches("What's the PRICE?")
    assert rule.matches("qual o preço?")
    assert not rule.matches("cool video")


def test_rule_word_match_is_stricter():
    rule = Rule.from_dict({"keywords": ["art"], "reply": "x", "match": "word"})
    assert rule.matches("i love art")
    assert not rule.matches("smart move")


def test_rule_exact_match():
    rule = Rule.from_dict({"keywords": ["link"], "reply": "x", "match": "exact"})
    assert rule.matches("  Link ")
    assert not rule.matches("send me the link please")


def test_plan_uses_first_matching_rule_with_dm():
    cfg = _cfg(rules=[PRICING])
    plan = plan_reply(_comment("how much is the price?"), cfg)
    assert plan.matched
    assert plan.rule_name == "pricing"
    assert plan.public_reply == "Sent prices to @ana!"
    assert plan.dm == "Prices: R$120"


def test_plan_falls_back_to_template_when_no_rule():
    cfg = _cfg(rules=[PRICING])
    plan = plan_reply(_comment("linda!"), cfg)
    assert not plan.matched
    assert plan.dm is None
    assert "@ana" in plan.public_reply


def test_only_rules_stays_silent_on_no_match():
    cfg = _cfg(rules=[PRICING], only_rules=True)
    plan = plan_reply(_comment("nice"), cfg)
    assert plan.public_reply is None
    assert plan.dm is None


def test_send_dm_false_suppresses_dm():
    cfg = _cfg(rules=[PRICING], send_dm=False)
    plan = plan_reply(_comment("price?"), cfg)
    assert plan.public_reply == "Sent prices to @ana!"
    assert plan.dm is None


def test_load_rules_from_config():
    cfg = _cfg(rules=[PRICING, {"keywords": "hi", "reply": "hey"}])
    rules = load_rules(cfg)
    assert len(rules) == 2
    assert rules[1].keywords == ["hi"]  # string coerced to list
