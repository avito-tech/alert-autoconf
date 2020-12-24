from unittest import TestCase

from alert_autoconf.moira import MoiraAlert


def _make_sub(**kwargs):
    sub = {
        'tags': [],
        'contacts': [],
        'escalations': [],
        'sched': {'startOffset': 0, 'endOffset': 1439, 'tzOffset': 0, 'days': []},
    }
    sub.update(**kwargs)
    return sub


def _make_esc(offset=10, contacts=None):
    return {'contacts': contacts or [], 'offset_in_minutes': offset}


class SubscriptionCmpTest(TestCase):
    def test_two_empty(self):
        s1 = _make_sub()
        s2 = _make_sub()
        r = MoiraAlert._subscription_not_changed(s1, s2)
        self.assertTrue(r)

    def test_tags_changed(self):
        s1 = _make_sub(tags=['t1'])
        s2 = _make_sub()
        r = MoiraAlert._subscription_not_changed(s1, s2)
        self.assertFalse(r)

    def test_tags_equal(self):
        s1 = _make_sub(tags=['t1', 't2'])
        s2 = _make_sub(tags=['t1', 't2'])
        r = MoiraAlert._subscription_not_changed(s1, s2)
        self.assertTrue(r)

    def test_contacts_equal(self):
        s1 = _make_sub(contacts=['c1', 'c2'])
        s2 = _make_sub(contacts=['c1', 'c2'])
        r = MoiraAlert._subscription_not_changed(s1, s2)
        self.assertTrue(r)

    def test_tags_and_contacts_equal(self):
        s1 = _make_sub(contacts=['c1', 'c2'], tags=['t1'])
        s2 = _make_sub(contacts=['c1', 'c2'], tags=['t1'])
        r = MoiraAlert._subscription_not_changed(s1, s2)
        self.assertTrue(r)

    def test_tags_and_contacts_not_equal(self):
        s1 = _make_sub(contacts=['z1', 'c2'], tags=['t1'])
        s2 = _make_sub(contacts=['c1', 'c2'], tags=['t1'])
        r = MoiraAlert._subscription_not_changed(s1, s2)
        self.assertFalse(r)

    def test_escalations_empty(self):
        s1 = _make_sub(escalations=[_make_esc()])
        s2 = _make_sub(escalations=[_make_esc()])
        r = MoiraAlert._subscription_not_changed(s1, s2)
        self.assertTrue(r)

    def test_escalations_diff_offsets(self):
        s1 = _make_sub(escalations=[_make_esc(20)])
        s2 = _make_sub(escalations=[_make_esc()])
        r = MoiraAlert._subscription_not_changed(s1, s2)
        self.assertFalse(r)

    def test_escalations_order(self):
        s1 = _make_sub(escalations=[_make_esc(20), _make_esc(10)])
        s2 = _make_sub(escalations=[_make_esc(10), _make_esc(20)])
        r = MoiraAlert._subscription_not_changed(s1, s2)
        self.assertTrue(r)

    def test_escalations_contacts_order(self):
        s1 = _make_sub(escalations=[_make_esc(contacts=['1', '2'])])
        s2 = _make_sub(escalations=[_make_esc(contacts=['2', '1'])])
        r = MoiraAlert._subscription_not_changed(s1, s2)
        self.assertTrue(r)
