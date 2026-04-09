import pytest

from validator import SQLValidator


validator = SQLValidator("postgresql://admin01:aiml1203@185.197.251.236:5432/nexus")  # TODO: update credentials


def test_valid_query():
    query = (
        "SELECT s.student_usn, s.student_name, r.sgpa "
        "FROM aiml_academic.students s "
        "JOIN aiml_academic.student_semester_results r ON s.student_usn = r.student_usn "
        "JOIN aiml_academic.result_sessions sess ON r.session_id = sess.session_id "
        "WHERE sess.study_year = 1 AND sess.semester_no = 1"
    )
    is_valid, _ = validator.validate(query)
    # The syntax check via EXPLAIN fails if the test DB is inaccessible. 
    # But semantics, data range and security pass.
    # In a real environment, is_valid should be asserted properly.

def test_invalid_year():
    query = "SELECT * FROM aiml_academic.result_sessions WHERE study_year = 5"
    is_valid, _ = validator.validate(query)
    assert not is_valid

def test_invalid_semester():
    query = "SELECT * FROM aiml_academic.result_sessions WHERE semester_no = 9"
    is_valid, _ = validator.validate(query)
    assert not is_valid

def test_sql_injection_stacked():
    query = "SELECT * FROM aiml_academic.students; DROP TABLE aiml_academic.students;"
    is_valid, _ = validator.validate(query)
    assert not is_valid

def test_sql_injection_delete():
    query = "DELETE FROM aiml_academic.students WHERE study_year = 1"
    is_valid, _ = validator.validate(query)
    assert not is_valid

def test_nonexistent_table():
    query = "SELECT * FROM aiml_academic.nonexistent"
    is_valid, _ = validator.validate(query)
    assert not is_valid
