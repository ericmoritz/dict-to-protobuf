from fp.monads.maybe import Maybe, Nothing
from google.protobuf.message import Message
from fp.collections import lookup
from fp import p, pp, c


class MissingKeyError(Exception):
    def __init__(self, key, pb):
        pb_name = _pb_name(pb)
        msg = "{key!r} not described in the {pb_name!r} message".format(**locals())
        Exception.__init__(self, msg)
        self.key = key
        self.pb = pb

class KeyTypeError(Exception):
    def __init__(self, key, pb, value):
        msg = "{key!r} is wrong type. Expected type {type!r} but got value: {value!r}".format(
            key=key, 
            type=type(pb),
            value=value
        )
        Exception.__init__(self, msg)
        self.key = key
        self.pb = pb


def dict_to_protobuf(mod, pb, data, strict=False, state=None):
    """
    Converts a dict to a protobuf message

    >>> import example_pb2
    >>> ex = dict_to_protobuf(
    ...     example_pb2,
    ...     example_pb2.Example(),
    ...     {'key': '1', 'values': ['1','2','3'], 'nested': {'value': '1'},
    ...      'nested_values': [{'value': '1'}, {'value': '2'}]}
    ... )
    >>> ex.key
    '1'

    >>> ex.values
    ['1', '2', '3']

    >>> ex.nested.value
    '1'

    >>> ex.nested_values[0].value
    '1'

    >>> ex.nested_values[1].value
    '2'

    Test the different ways that strict=True will
    throw an error

    At the root:

    >>> ex = dict_to_protobuf(
    ...     example_pb2,
    ...     example_pb2.Example(),
    ...     {'unknown-key': 1},
    ...     strict=True)
    Traceback (most recent call last):
        ...
    MissingKeyError: 'unknown-key' not described in the 'example_pb2.Example' message

    In a nested message:

    >>> ex = dict_to_protobuf(
    ...     example_pb2,
    ...     example_pb2.Example(),
    ...     {'nested': {'unknown-key': 1}},
    ...     strict=True)
    Traceback (most recent call last):
        ...
    MissingKeyError: 'unknown-key' not described in the 'example_pb2.Example.Nested' message

    In a repeated nested message:

    >>> ex = dict_to_protobuf(
    ...     example_pb2,
    ...     example_pb2.Example(),
    ...     {'nested_values': [{'unknown-key': 1}]},
    ...     strict=True)
    Traceback (most recent call last):
        ...
    MissingKeyError: 'unknown-key' not described in the 'example_pb2.Example.Nested' message

    """
    if state is None:
        state={'strict': strict}
    else:
        strict = state.get('strict', False)

    for key, value in data.iteritems():
        enforce_strictness(strict, pb, key)

        if field_exists(pb, key):
            if is_message(pb, key, value):
                update_message(mod, pb, key, value, state)
            elif is_repeated(pb, key, value):
                update_repeated(mod, pb, key, value, state)
            elif is_value(pb, key, value):
                update_value(mod, pb, key, value, state)
    return pb


def enforce_strictness(strict, pb, key):
    if strict and not field_exists(pb, key):
        raise MissingKeyError(key, pb)


def is_message(pb, key, value):
    return type(value) is dict 


def is_repeated(pb, key, value):
    return type(value) is list

        
def is_value(pb, key, value):
    return not is_message(pb, key, value) and not is_repeated(pb, key, value)


def update_message(mod, pb, key, value, state):
    pb_field = field(pb, key)
    if pb_field.is_nothing:
        raise MissingKeyError(key, pb)
    elif not isinstance(pb_field.from_just, Message):
        raise KeyTypeError(key, pb_field.from_just, value)

    dict_to_protobuf(mod, getattr(pb, key), value, state=state)


def update_repeated(mod, pb, key, values, state):
    clsM = load_pb_class(mod, pb, key)

    if clsM.is_just:
        cls = clsM.from_just
        for value in values:
            obj = getattr(pb, key).add()
            dict_to_protobuf(mod, obj, value, state=state)
    else:
        for value in values:
            getattr(pb, key).append(value)


def update_value(mod, pb, key, value, state):
    try:
        setattr(pb, key, value)
    except Exception, err:
        raise Exception("Error setting {key!r} to {value!r}: {err}".format(
                key=key,
                value=value,
                err=err))


def maybe_getattr(attr, obj):
    return Maybe.catch(lambda: getattr(obj, attr))


def maybe_getnested_attr(obj, *attrs):
    m = Maybe.ret(obj)
    for attr in attrs:
        m = m.bind(p(maybe_getattr, attr))
    return m


def load_pb_class(mod, pb, key):
    """
    Loads a class for a key

    >>> import example_pb2
    >>> load_pb_class(example_pb2, example_pb2.Example(), 'nested')
    Just(<class 'example_pb2.Nested'>)

    >>> load_pb_class(example_pb2, example_pb2.Example(), 'nested_values')
    Just(<class 'example_pb2.Nested'>)
    >>> load_pb_class(example_pb2, example_pb2.Example(), 'xxx')
    Nothing
    """
    return lookup(Maybe, _fields_by_name(pb), key).bind(
        pp(maybe_getnested_attr, 'message_type', 'full_name')).bind(
        lambda full_name: maybe_getnested_attr(mod, *full_name.split('.')))


def field_exists(pb, key):
    return field(pb, key).is_just

def field(pb, key):
    assert isinstance(pb, Message), "{key!r} is expected to be an object but got type {type!r}".format(
        key=key,
        type=type(pb)
    )
    return Maybe.catch(lambda: getattr(pb, key))


def _fields_by_name(pb):
    return pb.DESCRIPTOR.fields_by_name


def _pb_name(pb):
    """
    >>> import example_pb2
    >>> _pb_name(example_pb2.Example)
    'example_pb2.Example'

    >>> _pb_name(example_pb2.Example.Nested)
    'example_pb2.Example.Nested'
    """
    mod = pb.__module__
    full_name = pb.DESCRIPTOR.full_name
    return '{mod}.{full_name}'.format(mod=mod, full_name=full_name)
