from services.ingredient_catalog import IngredientMatch, validated_matches
from services.ingredient_names import canonical_ingredients


def match(alias, target):
    return IngredientMatch(alias=alias, canonical_name=target)


def test_batch_can_establish_one_name_for_two_new_labels():
    names = ["mướp đắng", "khổ qua"]
    mapping = validated_matches(names, [], [match(name, "khổ qua") for name in names])
    assert canonical_ingredients(names, mapping) == ["khổ qua"]


def test_existing_target_and_invalid_or_ambiguous_proposals():
    names = ["mướp đắng", "chả", "bì", "gân"]
    proposals = [match("mướp đắng", "khổ qua"), match("chả", "chả lụa"),
                 match("bì", "gân"), match("gân", "bì"), match("chả", "chả")]
    assert validated_matches(names, ["khổ qua"], proposals) == {"mướp đắng": "khổ qua"}


def test_unrequested_alias_or_invented_target_cannot_enter_catalog():
    proposals = [match("hành", "hành"), match("hành hoa", "hành ta")]
    assert validated_matches(["hành hoa"], [], proposals) == {}
