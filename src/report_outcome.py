"""Distinguish native loop completion from delivery without discarding either."""


def delivery_outcome(native_status, native_error_code, report, automatic_passed, *, source_count, validation_checks):
    result = dict(native_status=native_status, native_error_code=native_error_code,
                  status=native_status, error_code=native_error_code)
    if not report.strip():
        result['delivery_status'] = 'not_delivered'
        result['delivery_error_code'] = ('no_admitted_evidence' if not source_count else
            'report_repair_exhausted' if validation_checks and not validation_checks[-1]['passed'] else 'empty_report')
        if native_status == 'succeeded':
            result.update(status='failed', error_code=result['delivery_error_code'])
    else:
        result['delivery_status'] = 'delivered' if automatic_passed else 'delivered_with_failed_checks'
        result['delivery_error_code'] = None if automatic_passed else 'report_checks_failed'
    return result
