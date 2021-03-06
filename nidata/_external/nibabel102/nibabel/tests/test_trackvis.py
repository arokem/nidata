''' Testing trackvis module '''

from StringIO import StringIO

import numpy as np

from .. import trackvis as tv
from ..volumeutils import swapped_code

from nose.tools import assert_true, assert_false, assert_equal, assert_raises

from numpy.testing import assert_array_equal, assert_array_almost_equal

from ..testing import parametric


@parametric
def test_write():
    streams = []
    out_f = StringIO()
    tv.write(out_f, [], {})
    yield assert_equal(out_f.getvalue(), tv.empty_header().tostring())
    out_f.truncate(0)
    # Write something not-default
    tv.write(out_f, [], {'id_string':'TRACKb'})
    # read it back
    out_f.seek(0)
    streams, hdr = tv.read(out_f)
    yield assert_equal(hdr['id_string'], 'TRACKb')
    # check that we can pass none for the header
    out_f.truncate(0)
    tv.write(out_f, [])
    out_f.truncate(0)
    tv.write(out_f, [], None)
    # check that we check input values
    out_f.truncate(0)
    yield assert_raises(tv.HeaderError,
           tv.write, out_f, [],{'id_string':'not OK'})
    yield assert_raises(tv.HeaderError,
           tv.write, out_f, [],{'version': 3})
    yield assert_raises(tv.HeaderError,
           tv.write, out_f, [],{'hdr_size': 0})


def test_write_scalars_props():
    # Test writing of scalar array with streamlines
    N = 6
    M = 2
    P = 4
    points = np.arange(N*3).reshape((N,3))
    scalars = np.arange(N*M).reshape((N,M)) + 100
    props = np.arange(P) + 1000
    # If scalars not same size for each point, error
    out_f = StringIO()
    streams = [(points, None, None),
               (points, scalars, None)]
    assert_raises(tv.DataError, tv.write, out_f, streams)
    out_f.seek(0)
    streams = [(points, np.zeros((N,M+1)), None),
               (points, scalars, None)]
    assert_raises(tv.DataError, tv.write, out_f, streams)
    # Or if scalars different N compared to points
    bad_scalars = np.zeros((N+1,M))
    out_f.seek(0)
    streams = [(points, bad_scalars, None),
               (points, bad_scalars, None)]
    assert_raises(tv.DataError, tv.write, out_f, streams)
    # Similarly properties must have the same length for each streamline
    out_f.seek(0)
    streams = [(points, scalars, None),
               (points, scalars, props)]
    assert_raises(tv.DataError, tv.write, out_f, streams)
    out_f.seek(0)
    streams = [(points, scalars, np.zeros((P+1,))),
               (points, scalars, props)]
    assert_raises(tv.DataError, tv.write, out_f, streams)
    # If all is OK, then we get back what we put in
    out_f.seek(0)
    streams = [(points, scalars, props),
               (points, scalars, props)]
    tv.write(out_f, streams)
    out_f.seek(0)
    back_streams, hdr = tv.read(out_f)
    for actual, expected in zip(streams, back_streams):
        for a_el, e_el in zip(actual, expected):
            assert_array_equal(a_el, e_el)


def streams_equal(stream1, stream2):
    if not np.all(stream1[0] == stream2[0]):
        return False
    if stream1[1] is None:
        if not stream2[1] is None:
            return False
    if stream1[2] is None:
        if not stream2[2] is None:
            return False
    if not np.all(stream1[1] == stream2[1]):
        return False
    if not np.all(stream1[2] == stream2[2]):
        return False
    return True


def streamlist_equal(streamlist1, streamlist2):
    if len(streamlist1) != len(streamlist2):
        return False
    for s1, s2 in zip(streamlist1, streamlist2):
        if not streams_equal(s1, s2):
            return False
    return True


def test_round_trip():
    out_f = StringIO()
    xyz0 = np.tile(np.arange(5).reshape(5,1), (1, 3))
    xyz1 = np.tile(np.arange(5).reshape(5,1) + 10, (1, 3))
    streams = [(xyz0, None, None), (xyz1, None, None)]
    tv.write(out_f, streams, {})
    out_f.seek(0)
    streams2, hdr = tv.read(out_f)
    assert_true(streamlist_equal(streams, streams2))
    # test that we can write in different endianness and get back same result
    out_f.seek(0)
    tv.write(out_f, streams, {}, swapped_code)
    out_f.seek(0)
    streams2, hdr = tv.read(out_f)
    assert_true(streamlist_equal(streams, streams2))
    # test that we can get out and pass in generators
    out_f.seek(0)
    streams3, hdr = tv.read(out_f, as_generator=True)
    # check this is a generator rather than a list
    assert_true(hasattr(streams3, 'next'))
    # but that it results in the same output
    assert_true(streamlist_equal(streams, list(streams3)))
    # write back in
    out_f.seek(0)
    streams3, hdr = tv.read(out_f, as_generator=True)
    # Now we need a new file object, because we're still using the old one for
    # our generator
    out_f_write = StringIO()
    tv.write(out_f_write, streams3, {})
    # and re-read just to check
    out_f_write.seek(0)
    streams2, hdr = tv.read(out_f_write)
    assert_true(streamlist_equal(streams, streams2))


@parametric
def test_empty_header():
    for endian in '<>':
        for version in (1, 2):
            hdr = tv.empty_header(endian, version)
            yield assert_equal(hdr['id_string'], 'TRACK')
            yield assert_equal(hdr['version'], version)
            yield assert_equal(hdr['hdr_size'], 1000)
            yield assert_array_equal(
                hdr['image_orientation_patient'],
                [0,0,0,0,0,0])
    hdr = tv.empty_header(version=2)
    yield assert_array_equal(hdr['vox_to_ras'], np.zeros((4,4)))
    hdr_endian = tv.endian_codes[tv.empty_header().dtype.byteorder]
    yield assert_equal(hdr_endian, tv.native_code)


@parametric
def test_get_affine():
    hdr = tv.empty_header()
    # default header gives useless affine
    yield assert_array_equal(tv.aff_from_hdr(hdr),
                             np.diag([0,0,0,1]))
    hdr['voxel_size'] = 1
    yield assert_array_equal(tv.aff_from_hdr(hdr),
                             np.diag([0,0,0,1]))
    # DICOM direction cosines
    hdr['image_orientation_patient'] = [1,0,0,0,1,0]
    yield assert_array_equal(tv.aff_from_hdr(hdr),
                             np.diag([-1,-1,1,1]))
    # RAS direction cosines
    hdr['image_orientation_patient'] = [-1,0,0,0,-1,0]
    yield assert_array_equal(tv.aff_from_hdr(hdr),
                             np.eye(4))
    # translations
    hdr['origin'] = [1,2,3]
    exp_aff = np.eye(4)
    exp_aff[:3,3] = [-1,-2,3]
    yield assert_array_equal(tv.aff_from_hdr(hdr),
                             exp_aff)
    # now use the easier vox_to_ras field
    hdr = tv.empty_header()
    aff = np.eye(4)
    aff[:3,:] = np.arange(12).reshape(3,4)
    hdr['vox_to_ras'] = aff
    yield assert_array_equal(tv.aff_from_hdr(hdr), aff)
    # mappings work too
    d = {'version': 1,
         'voxel_size': np.array([1,2,3]),
         'image_orientation_patient': np.array([1,0,0,0,1,0]),
         'origin': np.array([10,11,12])}
    aff = tv.aff_from_hdr(d)


@parametric
def test_aff_to_hdr():
    for version in (1, 2):
        hdr = {'version': version}
        affine = np.diag([1,2,3,1])
        affine[:3,3] = [10,11,12]
        tv.aff_to_hdr(affine, hdr)
        yield assert_array_almost_equal(tv.aff_from_hdr(hdr), affine)
        # put flip into affine
        aff2 = affine.copy()
        aff2[:,2] *=-1
        tv.aff_to_hdr(aff2, hdr)
        yield assert_array_almost_equal(tv.aff_from_hdr(hdr), aff2)
        if version == 2:
            yield assert_array_almost_equal(hdr['vox_to_ras'], aff2)


@parametric
def test_tv_class():
    tvf = tv.TrackvisFile([])
    yield assert_equal(tvf.streamlines, [])
    yield assert_true(isinstance(tvf.header, np.ndarray))
    yield assert_equal(tvf.endianness, tv.native_code)
    yield assert_equal(tvf.filename, None)
    out_f = StringIO()
    tvf.to_file(out_f)
    yield assert_equal(out_f.getvalue(), tv.empty_header().tostring())
    out_f.truncate(0)
    # Write something not-default
    tvf = tv.TrackvisFile([], {'id_string':'TRACKb'})
    tvf.to_file(out_f)
    # read it back
    out_f.seek(0)
    tvf_back = tv.TrackvisFile.from_file(out_f)
    yield assert_equal(tvf_back.header['id_string'], 'TRACKb')
    # check that we check input values
    out_f.truncate(0)
    yield assert_raises(tv.HeaderError,
                        tv.TrackvisFile,
                        [],{'id_string':'not OK'})
    yield assert_raises(tv.HeaderError,
                        tv.TrackvisFile,
                        [],{'version': 3})
    yield assert_raises(tv.HeaderError,
                        tv.TrackvisFile,
                        [],{'hdr_size':0})
    affine = np.diag([1,2,3,1])
    affine[:3,3] = [10,11,12]
    tvf.set_affine(affine)
    yield assert_true(np.all(tvf.get_affine() == affine))
    # Test that we raise an error with an iterator
    yield assert_raises(tv.TrackvisFileError,
                        tv.TrackvisFile,
                        iter([]))
