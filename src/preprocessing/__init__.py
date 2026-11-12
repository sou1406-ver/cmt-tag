"""Configurable text views for experiments; raw observations remain immutable."""

VERSIONS=('basic_v1','plain_text_v1','plain_text_v3','plain_text_v3_1')


def preprocess(text,version='plain_text_v3_1',**options):
    """Dispatch unchanged version engines; does not approve or update annotation.

    Returns a uniform text_normalized/version/details envelope. Version-specific
    options are forwarded to that engine, which validates its existing contract.
    Historical imports and results remain available at their original paths.
    """
    if version=='basic_v1':
        from .normalization import normalize
        value=normalize(text,**options)
        return dict(text_normalized=value,version=version,details={})
    if version=='plain_text_v1':
        from .plain_text import preprocess as engine
    elif version=='plain_text_v3':
        from .plain_text_v3 import preprocess as engine
    elif version=='plain_text_v3_1':
        from .final_normalization import normalize as engine
    else:raise ValueError('Unsupported preprocessing version: '+str(version))
    details=engine(text,**options)
    return dict(text_normalized=details['text_normalized'] if version=='plain_text_v3_1' else details['text_clean'],version=version,details=details)
