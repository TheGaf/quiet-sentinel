import unittest
from quiet_sentinel import Sentinel

class SentinelTests(unittest.TestCase):
    def test_learning_and_anomaly(self):
        s=Sentinel(cooldown=60)
        for i in range(6):
            self.assertEqual(s.observe('node','cpu',20+i%2,at=f'2026-10-20T10:00:0{i}+00:00')['state'],'learning' if i<5 else 'normal')
        self.assertEqual(s.observe('node','cpu',99,at='2026-10-20T10:00:10+00:00')['state'],'alert')
        self.assertEqual(s.observe('node','cpu',100,at='2026-10-20T10:00:20+00:00')['state'],'suppressed')
    def test_series_separate(self):
        s=Sentinel()
        for i in range(8):
            s.observe('nodeA','cpu',20)
        self.assertEqual(s.observe('nodeB','cpu',90)['state'],'learning')
    def test_stable_baseline(self):
        s=Sentinel()
        for i in range(12):
            s.observe('nodeA','temp',35)
        self.assertEqual(s.observe('nodeA','temp',35)['state'],'normal')
if __name__ == '__main__': unittest.main()
