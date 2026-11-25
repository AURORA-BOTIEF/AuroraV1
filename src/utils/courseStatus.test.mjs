import assert from 'node:assert/strict';
import test from 'node:test';
import { presentCourseStatus } from './courseStatus.mjs';

test('needs_review is not shown as a successful delivery', () => {
    const presented = presentCourseStatus({
        status: 'FAILED',
        quality_status: 'needs_review',
        needs_review: true,
        error: 'NEEDS_REVIEW 01-00-01 B1: Ventas_MultiRegional_2024.xlsx',
    });
    assert.equal(presented.code, 'needs_review');
    assert.equal(presented.label, 'NECESITA REVISIÓN');
    assert.match(presented.headline, /no se entregó/);
    assert.match(presented.detail, /Ventas_MultiRegional_2024/);
});

test('a succeeded execution that still carries the flag is not a clean pass', () => {
    const presented = presentCourseStatus({
        status: 'SUCCEEDED',
        lab_quality_needs_review: true,
        needs_review: true,
        quality_status: 'needs_review',
        error: 'NEEDS_REVIEW A2',
    });
    assert.equal(presented.code, 'needs_review');
});

test('low-confidence warnings do not change a passed course', () => {
    const presented = presentCourseStatus({
        status: 'SUCCEEDED',
        quality_status: 'passed',
        needs_review: false,
        quality_warnings: [{ lab_id: '01-00-01' }],
    });
    assert.equal(presented.code, 'passed');
    assert.equal(presented.headline, '');
});

test('a generic failure stays failed', () => {
    const presented = presentCourseStatus({
        status: 'FAILED',
        quality_status: 'failed',
        error: 'timeout',
    });
    assert.equal(presented.code, 'failed');
    assert.equal(presented.detail, 'timeout');
});
