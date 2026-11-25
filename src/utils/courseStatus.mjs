/** Client-visible course status. needs_review is not a successful delivery. */

export function presentCourseStatus(payload) {
    const body = payload || {};
    const quality = body.quality_status || body.course_status;
    const needsReview = body.needs_review === true || quality === 'needs_review';

    if (needsReview) {
        const detail = body.error || body.quality_summary || '';
        return {
            label: 'NECESITA REVISIÓN',
            code: 'needs_review',
            tone: 'needs_review',
            headline: 'El curso no se entregó: hay laboratorios con hallazgos de alta confianza que necesitan revisión.',
            detail: typeof detail === 'string' ? detail : '',
        };
    }

    if (body.status === 'SUCCEEDED' || quality === 'passed') {
        return {
            label: 'SUCCEEDED',
            code: 'passed',
            tone: 'passed',
            headline: '',
            detail: '',
        };
    }

    if (body.status === 'FAILED' || quality === 'failed') {
        const detail = body.error || '';
        return {
            label: 'FAILED',
            code: 'failed',
            tone: 'failed',
            headline: 'La generación falló.',
            detail: typeof detail === 'string' ? detail : '',
        };
    }

    if (body.status === 'RUNNING') {
        return { label: 'RUNNING', code: 'running', tone: 'running', headline: '', detail: '' };
    }

    return {
        label: body.status || 'UNKNOWN',
        code: 'pending',
        tone: 'pending',
        headline: '',
        detail: '',
    };
}
