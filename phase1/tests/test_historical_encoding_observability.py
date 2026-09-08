import pytest
from phase1.historical_encoding_observability import summarize, truncate


def node(step, tokens, code='a', parents=(0,)):
    return dict(step=step, parents=list(parents), code_sha=code*64, tokens=tuple(tokens))


def run(nodes):
    return dict(task='synthetic-task', component='synthetic-component', nodes=nodes)


def test_no_truncation_and_unique_siblings():
    r = summarize([run([node(1, [1, 2]), node(2, [1, 3], 'b'), node(3, [4], 'c', ())])])
    assert r['programs'] == 3 and r['same_parent_nonempty_pairs'] == 1
    assert r['byte_distinct_sibling_pairs'] == 1
    assert all(c['truncated_programs'] == c['encoded_equal_sibling_pairs'] == 0 for c in r['contexts'])
    assert all(c['retained_token_fraction'] == 1 for c in r['contexts'])


def test_middle_difference_collision_only_at_small_context():
    a = [1]*1000 + [2]*1000 + [3]*2000
    b = [1]*1000 + [4]*1000 + [3]*2000
    r = summarize([run([node(1, a), node(2, b, 'b')])])
    assert r['contexts'][0]['truncation_induced_equal_pairs'] == 1
    assert r['contexts'][1]['truncation_induced_equal_pairs'] == 0
    assert r['full_token_equal_byte_distinct_sibling_pairs'] == 0


def test_full_token_collision_is_not_truncation_induced():
    r = summarize([run([node(1, [1, 2]), node(2, [1, 2], 'b')])])
    assert r['full_token_equal_byte_distinct_sibling_pairs'] == 1
    assert all(c['encoded_equal_sibling_pairs'] == 1 and c['truncation_induced_equal_pairs'] == 0 for c in r['contexts'])


def test_duplicate_code_counted_but_not_distinct():
    r = summarize([run([node(1, [1, 2]), node(2, [1, 2])])])
    assert r['same_parent_nonempty_pairs'] == 1 and r['byte_distinct_sibling_pairs'] == 0


@pytest.mark.parametrize('length', [1, 2048, 2049, 8192, 8193, 16384, 16385])
def test_truncation_matches_mask_reference(length):
    tokens = list(range(length))
    for limit in (2048, 8192, 16384):
        expected = tuple(x for i, x in enumerate(tokens) if length <= limit or i < limit//4 or i >= length-(limit-limit//4))
        assert truncate(tokens, limit) == expected


def test_reject_outcomes():
    n = node(1, [1, 2]); n['label'] = 'forbidden'
    with pytest.raises(AssertionError): summarize([run([n])])


def test_order_invariance():
    nodes = [node(1, [1]), node(2, [2], 'b')]
    assert summarize([run(nodes)]) == summarize([run(list(reversed(nodes)))])
