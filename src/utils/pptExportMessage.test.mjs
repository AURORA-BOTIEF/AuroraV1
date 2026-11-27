import assert from 'node:assert/strict';
import test from 'node:test';
import { pptExportMessage } from './pptExportMessage.mjs';

test('a 422 explains the quality rejection in Spanish by default', () => {
    const message = pptExportMessage(422, {
        error: 'PPT quality validation failed',
        quality_report: { issues: [{ code: 'empty_table', message: 'tabla vacía' }] },
    }, 'es');
    assert.match(message, /no se exportó/);
    assert.match(message, /tabla vacía/);
    assert.doesNotMatch(message, /PPT quality validation failed/);
});

test('a 422 can be explained in English', () => {
    const message = pptExportMessage(422, {
        error: 'PPT quality validation failed',
        quality_report: { issues: [{ code: 'duplicate', message: 'duplicate slide' }] },
    }, 'en');
    assert.match(message, /was not exported/);
    assert.match(message, /duplicate slide/);
});
