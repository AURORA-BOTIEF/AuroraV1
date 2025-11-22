import React from 'react';
import { useParams, useSearchParams, useNavigate } from 'react-router-dom';
import BookEditor from './BookEditor';

function BookEditorPage() {
    const { projectFolder } = useParams();
    const [searchParams] = useSearchParams();
    const navigate = useNavigate();

    const bookType = searchParams.get('bookType') || 'theory';

    const handleClose = () => {
        navigate(-1); // Go back to previous page
    };

    return (
        <div style={{ width: '100%', height: '100vh', backgroundColor: '#f5f5f5' }}>
            <BookEditor
                projectFolder={projectFolder}
                bookType={bookType}
                onClose={handleClose}
            />
        </div>
    );
}

export default BookEditorPage;
