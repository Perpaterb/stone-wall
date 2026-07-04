from app.stones.dummy import generate_dummy_stone_dicts


def test_seedable_reproducible():
    a = generate_dummy_stone_dicts(50, seed=7)
    b = generate_dummy_stone_dicts(50, seed=7)
    assert a == b


def test_different_seeds_differ():
    a = generate_dummy_stone_dicts(50, seed=1)
    b = generate_dummy_stone_dicts(50, seed=2)
    assert a != b


def test_sizes_in_range_and_width_is_longer():
    for s in generate_dummy_stone_dicts(300, seed=3):
        assert 10.0 <= s["height_cm"] <= 40.0
        assert 10.0 <= s["width_cm"] <= 40.0
        assert s["width_cm"] >= s["height_cm"]
        assert s["area_cm2"] > 0
        assert len(s["polygon"]) == 4
