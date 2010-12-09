import unittest
import gc
import re

from pympler.tracker import ClassTracker
import pympler.process

class Empty:
    pass

class Foo:
    def __init__(self):
        self.foo = 'foo'

class Bar(Foo):
    def __init__(self):
        Foo.__init__(self)
        self.bar = 'bar'

class FooNew(object):
    def __init__(self):
        self.foo = 'foo'

class BarNew(FooNew):
    def __init__(self):
        super(BarNew, self).__init__()


class TrackObjectTestCase(unittest.TestCase):

    def setUp(self):
        self.tracker = ClassTracker()

    def tearDown(self):
        self.tracker.detach_all()

    def test_track_object(self):
        """Test object registration.
        """
        foo = Foo()
        bar = Bar()

        self.tracker.track_object(foo)
        self.tracker.track_object(bar)

        self.assert_(id(foo) in self.tracker.objects)
        self.assert_(id(bar) in self.tracker.objects)

        self.assert_('Foo' in self.tracker.index)
        self.assert_('Bar' in self.tracker.index)

        self.assertEqual(self.tracker.objects[id(foo)].ref(),foo)
        self.assertEqual(self.tracker.objects[id(bar)].ref(),bar)

    def test_type_errors(self):
        """Test intrackable objects.
        """
        i = 42
        j = 'Foobar'
        k = [i,j]
        l = {i: j}

        self.assertRaises(TypeError, self.tracker.track_object, i)
        self.assertRaises(TypeError, self.tracker.track_object, j)
        self.assertRaises(TypeError, self.tracker.track_object, k)
        self.assertRaises(TypeError, self.tracker.track_object, l)

        self.assert_(id(i) not in self.tracker.objects)
        self.assert_(id(j) not in self.tracker.objects)
        self.assert_(id(k) not in self.tracker.objects)
        self.assert_(id(l) not in self.tracker.objects)

    def test_track_by_name(self):
        """Test registering objects by name.
        """
        foo = Foo()

        self.tracker.track_object(foo, name='Foobar')

        self.assert_('Foobar' in self.tracker.index        )
        self.assertEqual(self.tracker.index['Foobar'][0].ref(),foo)

    def test_keep(self):
        """Test lifetime of tracked objects.
        """
        foo = Foo()
        bar = Bar()

        self.tracker.track_object(foo, keep=1)
        self.tracker.track_object(bar)
       
        idfoo = id(foo)
        idbar = id(bar)

        del foo
        del bar

        self.assert_(self.tracker.objects[idfoo].ref() is not None)
        self.assert_(self.tracker.objects[idbar].ref() is None)

    def test_mixed_tracking(self):
        """Test mixed instance and class tracking.
        """
        foo = Foo()
        self.tracker.track_object(foo)
        self.tracker.create_snapshot()
        self.tracker.track_class(Foo)
        objs = []
        for _ in range(10):
            objs.append(Foo())
        self.tracker.create_snapshot()

    def test_recurse(self):
        """Test recursive sizing and saving of referents.
        """
        foo = Foo()

        self.tracker.track_object(foo, resolution_level=1)
        self.tracker.create_snapshot()

        fp = self.tracker.objects[id(foo)].footprint[-1]
        refs = fp[1].refs
        dref = [r for r in refs if r.name == '__dict__']
        self.assertEqual(len(dref),1)
        dref = dref[0]
        self.assert_(dref.size > 0, dref.size)
        self.assert_(dref.flat > 0, dref.flat)
        self.assertEqual(dref.refs,())

        # Test track_change and more fine-grained resolution
        self.tracker.track_change(foo, resolution_level=2)
        self.tracker.create_snapshot()

        fp = self.tracker.objects[id(foo)].footprint[-1]
        refs = fp[1].refs
        dref = [r for r in refs if r.name == '__dict__']
        self.assertEqual(len(dref),1)
        dref = dref[0]
        namerefs = [r.name for r in dref.refs]
        self.assert_('[K] foo' in namerefs, namerefs)
        self.assert_("[V] foo: 'foo'" in namerefs, namerefs)

class SnapshotTestCase(unittest.TestCase):

    def setUp(self):
        self.tracker = ClassTracker()

    def tearDown(self):
        self.tracker.stop_periodic_snapshots()
        self.tracker.clear()

    def test_timestamp(self):
        """Test timestamp of snapshots.
        """
        foo = Foo()
        bar = Bar()

        self.tracker.track_object(foo)
        self.tracker.track_object(bar)

        self.tracker.create_snapshot()
        self.tracker.create_snapshot()
        self.tracker.create_snapshot()

        refts = [fp.timestamp for fp in self.tracker.footprint]
        for to in self.tracker.objects.values():
            ts = [t for (t,sz) in to.footprint[1:]]
            self.assertEqual(ts,refts)

    def test_snapshot_members(self):
        """Test existence and value of snapshot members.
        """
        foo = Foo()
        self.tracker.track_object(foo)
        self.tracker.create_snapshot()

        fp = self.tracker.footprint[0]
        self.assert_(fp.overhead > 0, fp.overhead)
        self.assert_(fp.tracked_total > 0, fp.tracked_total)
        self.assert_(fp.asizeof_total > 0, fp.asizeof_total)
        self.assert_(fp.asizeof_total >= fp.tracked_total)

        if pympler.process.is_available():
            self.assert_(fp.system_total.vsz > 0)
            self.assert_(fp.system_total.rss > 0)
            self.assert_(fp.system_total.vsz >= fp.system_total.rss)
            self.assert_(fp.system_total.vsz > fp.overhead)
            self.assert_(fp.system_total.vsz > fp.tracked_total)
            self.assert_(fp.system_total.vsz > fp.asizeof_total)

    def test_desc(self):
        """Test footprint description.
        """
        self.tracker.create_snapshot()
        self.tracker.create_snapshot('alpha')
        self.tracker.create_snapshot(description='beta')
        self.tracker.create_snapshot(42)

        self.assertEqual(len(self.tracker.footprint), 4)
        self.assertEqual(self.tracker.footprint[0].desc, '')
        self.assertEqual(self.tracker.footprint[1].desc, 'alpha')
        self.assertEqual(self.tracker.footprint[2].desc, 'beta')
        self.assertEqual(self.tracker.footprint[3].desc, '42')

    def test_background_monitoring(self):
        """Test background monitoring.
        """
        import time

        self.tracker.start_periodic_snapshots(0.1)
        self.assertEqual(self.tracker._periodic_thread.interval, 0.1)
        self.assertEqual(self.tracker._periodic_thread.getName(), 'BackgroundMonitor')
        for x in range(10): # try to interfere
            self.tracker.create_snapshot(str(x))
        time.sleep(0.5)
        self.tracker.start_periodic_snapshots(0.2)
        self.assertEqual(self.tracker._periodic_thread.interval, 0.2)
        self.tracker.stop_periodic_snapshots()
        self.assert_(self.tracker._periodic_thread is None)
        self.assert_(len(self.tracker.footprint) > 10)


class TrackClassTestCase(unittest.TestCase):

    def setUp(self):
        self.tracker = ClassTracker()

    def tearDown(self):
        self.tracker.stop_periodic_snapshots()
        self.tracker.clear()

    def test_type_errors(self):
        """Test invalid parameters for class tracking.
        """
        i = 42
        j = 'Foobar'
        k = [i,j]
        l = {i: j}
        foo = Foo()
        bar = Bar()

        self.assertRaises(TypeError, self.tracker.track_class, i)
        self.assertRaises(TypeError, self.tracker.track_class, j)
        self.assertRaises(TypeError, self.tracker.track_class, k)
        self.assertRaises(TypeError, self.tracker.track_class, l)
        self.assertRaises(TypeError, self.tracker.track_class, foo)
        self.assertRaises(TypeError, self.tracker.track_class, bar)

        self.assert_(id(i) not in self.tracker.objects)
        self.assert_(id(j) not in self.tracker.objects)
        self.assert_(id(k) not in self.tracker.objects)
        self.assert_(id(l) not in self.tracker.objects)

    def test_track_class(self):
        """Test tracking objects through classes.
        """
        self.tracker.track_class(Foo)
        self.tracker.track_class(Bar)
        self.tracker.track_class(Empty)
        self.tracker.track_class(Foo)

        foo = Foo()
        bar = Bar()
        empty = Empty()

        self.assert_(id(foo) in self.tracker.objects)
        self.assert_(id(bar) in self.tracker.objects)
        self.assert_(id(empty) in self.tracker.objects)

    def test_track_class_new(self):
        """Test tracking new style classes.
        """
        self.tracker.track_class(FooNew)
        self.tracker.track_class(BarNew)

        foo = FooNew()
        bar = BarNew()

        self.assert_(id(foo) in self.tracker.objects)
        self.assert_(id(bar) in self.tracker.objects)

    def test_track_by_name(self):
        """Test registering objects by name.
        """
        self.tracker.track_class(Foo, name='Foobar')

        foo = Foo()

        self.assert_('Foobar' in self.tracker.index        )
        self.assertEqual(self.tracker.index['Foobar'][0].ref(),foo)

    def test_keep(self):
        """Test lifetime of tracked objects.
        """
        self.tracker.track_class(Foo, keep=1)
        self.tracker.track_class(Bar)

        foo = Foo()
        bar = Bar()
       
        idfoo = id(foo)
        idbar = id(bar)

        del foo
        del bar

        self.assert_(self.tracker.objects[idfoo].ref() is not None)
        self.assert_(self.tracker.objects[idbar].ref() is None)

    def test_trace(self):
        """Test instantiation tracing of tracked objects.
        """
        from inspect import stack

        self.tracker.track_class(Foo, trace=True)
        self.tracker.track_class(BarNew, trace=True)

        foo = Foo()
        bar = BarNew()
       
        idfoo = id(foo)
        idbar = id(bar)

        trace = []
        st = stack()
        try:
            for fr in st:
                trace.insert(0, fr[1:])
        finally:
            del st

        self.assertEqual(self.tracker.objects[idfoo].trace[-1][3][0].strip(),"foo = Foo()")
        self.assertEqual(self.tracker.objects[idfoo].trace[:-1],trace[:-1], trace)
        self.assertEqual(self.tracker.objects[idbar].trace[:-1],trace[:-1], trace)

    def test_detach(self):
        """Test detaching from tracked classes.
        """
        self.tracker.track_class(Foo)
        self.tracker.track_class(Bar)

        foo = Foo()
        bar = Bar()

        self.assert_(id(foo) in self.tracker.objects)
        self.assert_(id(bar) in self.tracker.objects)

        self.tracker.detach_class(Foo)
        self.tracker.detach_class(Bar)

        foo2 = Foo()
        bar2 = Bar()
    
        self.assert_(id(foo2) not in self.tracker.objects)
        self.assert_(id(bar2) not in self.tracker.objects)

        self.assertRaises(KeyError, self.tracker.detach_class, Foo)

    def test_change_name(self):
        """Test modifying name.
        """
        self.tracker.track_class(Foo, name='Foobar')
        self.tracker.track_class(Foo, name='Baz')
        foo = Foo()

        self.assert_('Foobar' not in self.tracker.index)
        self.assert_('Baz' in self.tracker.index)
        self.assertEqual(self.tracker.index['Baz'][0].ref(),foo)


if __name__ == "__main__":
    suite = unittest.TestSuite()
    tclasses = [ TrackObjectTestCase,
                 TrackClassTestCase,
                 SnapshotTestCase
               ]
    for tclass in tclasses:
        names = unittest.getTestCaseNames(tclass, 'test_')
        suite.addTests(map(tclass, names))
    if not unittest.TextTestRunner().run(suite).wasSuccessful():
        sys.exit(1)
