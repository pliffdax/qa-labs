from run_cases import expected_outcome


def write_result(tmp_path, body):
    path = tmp_path/'result.xml'
    path.write_text('<testsuites><testsuite><testcase>'+body+'</testcase></testsuite></testsuites>')
    return path


def test_failed_parser_is_not_a_successful_low_rate_case(tmp_path):
    path = write_result(tmp_path, '<failure message="ValueError: broken parser"/>')
    assert not expected_outcome('low-rate', 1, path)


def test_intended_threshold_failure_is_recognized(tmp_path):
    path = write_result(tmp_path, '<failure message="AssertionError: Transfer &lt;= 2 MiB"/>')
    assert expected_outcome('low-rate', 1, path)


def test_connection_refusal_is_distinct_from_fixture_error(tmp_path):
    path = write_result(tmp_path, '<failure message="AssertionError: iperf3 failed (exit 1): Connection refused"/>')
    assert expected_outcome('closed-port', 1, path)
    path = write_result(tmp_path, '<error message="SSH unavailable"/>')
    assert not expected_outcome('closed-port', 1, path)


def test_quoted_threshold_assert_does_not_hide_wrong_failure(tmp_path):
    path = write_result(tmp_path, '<failure message="AssertionError: Missing measurement coverage">'
                        'Source excerpt: assert transfer, Transfer &lt;= 2 MiB</failure>')
    assert not expected_outcome('low-rate', 1, path)
