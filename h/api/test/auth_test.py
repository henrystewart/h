# -*- coding: utf-8 -*-

import datetime

from jwt import InvalidTokenError
import mock
import pytest

from h.api import auth
from h.api.models.token import API_TOKEN_PREFIX

generate_jwt_fixtures = pytest.mark.usefixtures('jwt')


@generate_jwt_fixtures
def test_generate_jwt_calls_encode(jwt):
    """It should pass the right arguments to encode()."""
    before = datetime.datetime.utcnow()
    request = mock_request()

    auth.generate_jwt(request, 3600)

    assert jwt.encode.call_args[0][0]['sub'] == 'acct:testuser@hypothes.is', (
        "It should encode the userid as 'sub'")
    after = datetime.datetime.utcnow() + datetime.timedelta(seconds=3600)
    assert before < jwt.encode.call_args[0][0]['exp'] < after, (
        "It should encode the expiration time as 'exp'")
    assert jwt.encode.call_args[0][0]['aud'] == request.host_url, (
        "It should encode request.host_url as 'aud'")
    assert jwt.encode.call_args[1]['algorithm'] == 'HS256', (
        "It should pass the right algorithm to encode()")


@generate_jwt_fixtures
def test_generate_jwt_when_authenticated_userid_is_None(jwt):
    """It should work when request.authenticated_userid is None."""
    request = mock_request()
    request.authenticated_userid = None

    auth.generate_jwt(request, 3600)

    assert jwt.encode.call_args[0][0]['sub'] is None


@generate_jwt_fixtures
def test_generate_jwt_returns_token(jwt):
    assert (auth.generate_jwt(mock_request(), 3600) ==
            jwt.encode.return_value)


userid_from_jwt_fixtures = pytest.mark.usefixtures('jwt')


@userid_from_jwt_fixtures
def test_userid_from_jwt_calls_decode(jwt):
    request = mock_request()
    auth.userid_from_jwt(u'abc123', request)

    assert jwt.decode.call_args[0] == (u'abc123',), (
        "It should pass the correct token to decode()")
    assert (jwt.decode.call_args[1]['key'] ==
            request.registry.settings['h.client_secret']), (
        "It should pass the right secret key to decode()")
    assert jwt.decode.call_args[1]['audience'] == request.host_url, (
        "It should pass the right audience to decode()")
    assert jwt.decode.call_args[1]['leeway'] == 240, (
        "It should pass the right leeway to decode()")
    assert jwt.decode.call_args[1]['algorithms'] == ['HS256'], (
        "It should pass the right algorithms to decode()")


@userid_from_jwt_fixtures
def test_userid_from_jwt_returns_sub_from_decode(jwt):
    jwt.decode.return_value = {'sub': 'acct:test_user@hypothes.is'}

    result = auth.userid_from_jwt(u'abc123', mock_request())

    assert result == 'acct:test_user@hypothes.is'


@userid_from_jwt_fixtures
def test_userid_from_jwt_returns_None_if_no_sub(jwt):
    jwt.decode.return_value = {}  # No 'sub' key.

    result = auth.userid_from_jwt(u'abc123', mock_request())

    assert result is None


@userid_from_jwt_fixtures
def test_userid_from_jwt_returns_None_if_decoding_fails(jwt):
    jwt.decode.side_effect = InvalidTokenError

    result = auth.userid_from_jwt(u'abc123', mock_request())

    assert result is None


def test_generate_jwt_userid_from_jwt_successful():
    """Test generate_jwt() and userid_from_jwt() together.

    Test that userid_from_jwt() successfully decodes tokens
    generated by generate_jwt().

    """
    token = auth.generate_jwt(mock_request(), 3600)
    userid = auth.userid_from_jwt(token, mock_request())

    assert userid == 'acct:testuser@hypothes.is'


def test_generate_jwt_userid_from_jwt_bad_token():
    """Test generate_jwt() and userid_from_jwt() together.

    Test that userid_from_jwt() correctly fails to decode a token
    generated by generate_jwt() using the wrong secret.

    """
    request = mock_request()
    request.registry.settings['h.client_secret'] = 'wrong'
    token = auth.generate_jwt(request, 3600)

    userid = auth.userid_from_jwt(token, mock_request())

    assert userid is None


userid_from_api_token_fixtures = pytest.mark.usefixtures('models')


@userid_from_api_token_fixtures
def test_userid_from_api_token_returns_None_when_token_doesnt_start_with_6879(
        models):
    assert auth.userid_from_api_token(u'abc123') is None
    assert not models.Token.get_by_value.called


@userid_from_api_token_fixtures
def test_userid_from_api_token_calls_get_by_value(models):
    token = API_TOKEN_PREFIX + u'abc123'
    auth.userid_from_api_token(token)

    models.Token.get_by_value.assert_called_once_with(token)


@userid_from_api_token_fixtures
def test_userid_from_api_token_returns_userid(models):
    assert (auth.userid_from_api_token(API_TOKEN_PREFIX + u'abc123') ==
            models.Token.get_by_value.return_value.userid)


@userid_from_api_token_fixtures
def test_userid_from_api_token_returns_None_when_token_is_not_found(models):
    models.Token.get_by_value.return_value = None

    assert (
        auth.userid_from_api_token(API_TOKEN_PREFIX + u'abc123') is None)


def mock_request(token=None):
    request = mock.Mock(authenticated_userid='acct:testuser@hypothes.is',
                        host_url='https://hypothes.is')
    request.registry.settings = {
        'h.client_id': 'id',
        'h.client_secret': 'secret'
    }
    if token:
        request.headers = {'Authorization': token}
    return request


@pytest.fixture
def jwt(request):
    patcher = mock.patch('h.api.auth.jwt', autospec=True)
    module = patcher.start()
    request.addfinalizer(patcher.stop)
    return module


@pytest.fixture
def models(request):
    patcher = mock.patch('h.api.auth.models', autospec=True)
    module = patcher.start()
    request.addfinalizer(patcher.stop)
    return module
