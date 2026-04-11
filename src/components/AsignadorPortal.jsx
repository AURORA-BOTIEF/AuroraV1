// src/components/AsignadorPortal.jsx
import React, { useState, useEffect } from 'react';
import './AsignadorPortal.css';

const API_BASE = import.meta.env.VITE_COURSE_GENERATOR_API_URL;

function AsignadorPortal() {
    const [activeTab, setActiveTab] = useState('by-course'); // 'by-course', 'by-user', or 'instructors'
    const [courses, setCourses] = useState([]);
    const [users, setUsers] = useState([]);
    const [instructors, setInstructors] = useState([]);
    const [assignments, setAssignments] = useState([]);
    const [loading, setLoading] = useState(true);
    const [selectedCourse, setSelectedCourse] = useState(null);
    const [selectedUser, setSelectedUser] = useState(null);
    const [selectedItems, setSelectedItems] = useState([]);
    const [searchTerm, setSearchTerm] = useState('');
    const [message, setMessage] = useState({ type: '', text: '' });
    const [csvEmails, setCsvEmails] = useState('');

    useEffect(() => {
        loadData();
    }, []);

    const loadData = async () => {
        setLoading(true);
        try {
            await Promise.all([
                loadCourses(),
                loadUsers(),
                loadInstructors(),
                loadAssignments()
            ]);
        } catch (error) {
            console.error('Error loading data:', error);
            showMessage('error', 'Error cargando datos: ' + error.message);
        } finally {
            setLoading(false);
        }
    };

    const loadCourses = async () => {
        const response = await fetch(`${API_BASE}/list-projects?limit=100`);
        if (!response.ok) throw new Error('Failed to load courses');
        const data = await response.json();
        setCourses(data.projects || []);
    };

    const loadUsers = async () => {
        const response = await fetch(`${API_BASE}/users?group=Estudiantes`);
        if (!response.ok) throw new Error('Failed to load users');
        const data = await response.json();
        setUsers(data.users || []);
    };

    const loadInstructors = async () => {
        try {
            const response = await fetch(`${API_BASE}/users?group=Instructores_Externos`);
            if (!response.ok) {
                // If no instructors group exists yet, just set empty array
                setInstructors([]);
                return;
            }
            const data = await response.json();
            setInstructors(data.users || []);
        } catch (err) {
            console.log('No instructors found yet');
            setInstructors([]);
        }
    };

    const loadAssignments = async () => {
        const response = await fetch(`${API_BASE}/assignments`);
        if (!response.ok) throw new Error('Failed to load assignments');
        const data = await response.json();
        setAssignments(data.assignments || []);
    };

    const showMessage = (type, text) => {
        setMessage({ type, text });
        setTimeout(() => setMessage({ type: '', text: '' }), 5000);
    };

    // Parse CSV emails (comma, semicolon, or newline separated)
    const parseEmails = (input) => {
        return input
            .split(/[,;\n]+/)
            .map(e => e.trim().toLowerCase())
            .filter(e => e && e.includes('@'));
    };

    const getCsvEmailCount = () => {
        return parseEmails(csvEmails).length;
    };

    const handleAssign = async () => {
        try {
            let body = {};

            if ((activeTab === 'by-course' || activeTab === 'instructors') && selectedCourse) {
                // Combine selected users and CSV emails
                const csvEmailList = parseEmails(csvEmails);
                const allUserIds = [...new Set([...selectedItems, ...csvEmailList])];

                if (allUserIds.length === 0) {
                    showMessage('error', 'Selecciona usuarios o ingresa emails para asignar');
                    return;
                }

                body = {
                    courseId: selectedCourse.folder,
                    userIds: allUserIds,
                    assignedBy: 'Asignador',
                    userType: activeTab === 'instructors' ? 'instructor' : 'student'
                };
            } else if (activeTab === 'by-user' && selectedUser && selectedItems.length > 0) {
                body = {
                    userId: selectedUser.email || selectedUser.username,
                    courseIds: selectedItems,
                    assignedBy: 'Asignador'
                };
            } else {
                showMessage('error', 'Selecciona elementos para asignar');
                return;
            }

            const response = await fetch(`${API_BASE}/assignments`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body)
            });

            if (!response.ok) throw new Error('Failed to create assignment');

            const result = await response.json();
            showMessage('success', `${result.assignments?.length || 0} asignaciones creadas`);
            setSelectedItems([]);
            setCsvEmails('');
            await loadAssignments();
        } catch (error) {
            console.error('Error assigning:', error);
            showMessage('error', 'Error al asignar: ' + error.message);
        }
    };

    const handleRemoveAssignment = async (userId, courseId) => {
        try {
            const response = await fetch(`${API_BASE}/assignments`, {
                method: 'DELETE',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ userId, courseId })
            });

            if (!response.ok) throw new Error('Failed to remove assignment');

            showMessage('success', 'Asignación eliminada');
            await loadAssignments();
        } catch (error) {
            console.error('Error removing assignment:', error);
            showMessage('error', 'Error al eliminar: ' + error.message);
        }
    };

    const toggleSelection = (item) => {
        setSelectedItems(prev =>
            prev.includes(item)
                ? prev.filter(i => i !== item)
                : [...prev, item]
        );
    };

    const getAssignedUsers = (courseId) => {
        return assignments.filter(a => a.courseId === courseId).map(a => a.userId);
    };

    const getAssignedCourses = (userId) => {
        return assignments.filter(a => a.userId === userId).map(a => a.courseId);
    };

    const filteredCourses = courses.filter(c =>
        c.title.toLowerCase().includes(searchTerm.toLowerCase()) ||
        c.folder.toLowerCase().includes(searchTerm.toLowerCase())
    );

    const filteredUsers = users.filter(u =>
        (u.email || u.username || '').toLowerCase().includes(searchTerm.toLowerCase())
    );

    const filteredInstructors = instructors.filter(u =>
        (u.email || u.username || '').toLowerCase().includes(searchTerm.toLowerCase())
    );

    if (loading) {
        return <div className="asignador-loading">Cargando...</div>;
    }

    return (
        <div className="asignador-portal">
            <div className="asignador-header">
                <h1>🎓 Portal de Asignación de Cursos</h1>
                <p>Asigna cursos a estudiantes e instructores externos</p>
            </div>

            {message.text && (
                <div className={`message ${message.type}`}>
                    {message.text}
                </div>
            )}

            <div className="tabs">
                <button
                    className={`tab ${activeTab === 'by-course' ? 'active' : ''}`}
                    onClick={() => { setActiveTab('by-course'); setSelectedItems([]); setSearchTerm(''); setCsvEmails(''); setSelectedCourse(null); }}
                >
                    📚 Por Curso (Estudiantes)
                </button>
                <button
                    className={`tab ${activeTab === 'by-user' ? 'active' : ''}`}
                    onClick={() => { setActiveTab('by-user'); setSelectedItems([]); setSearchTerm(''); setCsvEmails(''); setSelectedUser(null); }}
                >
                    👤 Por Usuario
                </button>
                <button
                    className={`tab ${activeTab === 'instructors' ? 'active' : ''}`}
                    onClick={() => { setActiveTab('instructors'); setSelectedItems([]); setSearchTerm(''); setCsvEmails(''); setSelectedCourse(null); }}
                >
                    👨‍🏫 Instructores Externos
                </button>
            </div>

            <div className="asignador-content">
                {activeTab === 'by-course' ? (
                    <div className="assignment-flow">
                        <div className="selection-panel">
                            <h3>1. Selecciona un Curso</h3>
                            <input
                                type="text"
                                placeholder="Buscar cursos..."
                                value={searchTerm}
                                onChange={(e) => setSearchTerm(e.target.value)}
                                className="search-input"
                            />
                            <div className="items-list">
                                {filteredCourses.map(course => (
                                    <div
                                        key={course.folder}
                                        className={`item-card ${selectedCourse?.folder === course.folder ? 'selected' : ''}`}
                                        onClick={() => { setSelectedCourse(course); setSelectedItems([]); setCsvEmails(''); }}
                                    >
                                        <div className="item-title">{course.title}</div>
                                        <div className="item-subtitle">{course.folder}</div>
                                        <div className="item-badge">
                                            {getAssignedUsers(course.folder).length} asignados
                                        </div>
                                    </div>
                                ))}
                            </div>
                        </div>

                        {selectedCourse && (
                            <div className="selection-panel">
                                <h3>2. Selecciona Estudiantes</h3>
                                <div className="selected-info">
                                    Curso: <strong>{selectedCourse.title}</strong>
                                </div>

                                {/* CSV Email Input */}
                                <div className="csv-input-section">
                                    <h4>📧 Asignar por Email (usuarios nuevos o existentes)</h4>
                                    <textarea
                                        placeholder="Ingresa emails separados por coma, punto y coma, o líneas nuevas. Ej:&#10;usuario1@email.com, usuario2@email.com&#10;usuario3@email.com"
                                        value={csvEmails}
                                        onChange={(e) => setCsvEmails(e.target.value)}
                                    />
                                    <small>Los usuarios serán pre-asignados. Cuando se registren, verán el curso automáticamente.</small>
                                    {getCsvEmailCount() > 0 && (
                                        <div className="csv-count">{getCsvEmailCount()} email(s) detectados</div>
                                    )}
                                </div>

                                <div className="divider"><span>o selecciona usuarios registrados</span></div>

                                <div className="items-list">
                                    {users.map(user => {
                                        const userId = user.email || user.username;
                                        const isAssigned = getAssignedUsers(selectedCourse.folder).includes(userId);
                                        const isSelected = selectedItems.includes(userId);

                                        return (
                                            <div
                                                key={userId}
                                                className={`item-card ${isSelected ? 'selected' : ''} ${isAssigned ? 'assigned' : ''}`}
                                                onClick={() => !isAssigned && toggleSelection(userId)}
                                            >
                                                <div className="item-title">{user.email || user.username}</div>
                                                <div className="item-subtitle">{user.name || 'Sin nombre'}</div>
                                                {isAssigned ? (
                                                    <button
                                                        className="remove-btn"
                                                        onClick={(e) => { e.stopPropagation(); handleRemoveAssignment(userId, selectedCourse.folder); }}
                                                    >
                                                        ✕ Quitar
                                                    </button>
                                                ) : (
                                                    <input
                                                        type="checkbox"
                                                        checked={isSelected}
                                                        onChange={() => toggleSelection(userId)}
                                                        onClick={(e) => e.stopPropagation()}
                                                    />
                                                )}
                                            </div>
                                        );
                                    })}
                                </div>
                                {(selectedItems.length > 0 || getCsvEmailCount() > 0) && (
                                    <button className="assign-btn" onClick={handleAssign}>
                                        ✓ Asignar {selectedItems.length + getCsvEmailCount()} estudiante(s)
                                    </button>
                                )}
                            </div>
                        )}
                    </div>
                ) : activeTab === 'instructors' ? (
                    /* INSTRUCTORES EXTERNOS TAB */
                    <div className="assignment-flow">
                        <div className="selection-panel">
                            <h3>1. Selecciona un Curso</h3>
                            <input
                                type="text"
                                placeholder="Buscar cursos..."
                                value={searchTerm}
                                onChange={(e) => setSearchTerm(e.target.value)}
                                className="search-input"
                            />
                            <div className="items-list">
                                {filteredCourses.map(course => (
                                    <div
                                        key={course.folder}
                                        className={`item-card ${selectedCourse?.folder === course.folder ? 'selected' : ''}`}
                                        onClick={() => { setSelectedCourse(course); setSelectedItems([]); setCsvEmails(''); }}
                                    >
                                        <div className="item-title">{course.title}</div>
                                        <div className="item-subtitle">{course.folder}</div>
                                        <div className="item-badge instructor">
                                            {getAssignedUsers(course.folder).length} asignados
                                        </div>
                                    </div>
                                ))}
                            </div>
                        </div>

                        {selectedCourse && (
                            <div className="selection-panel">
                                <h3>2. Asignar Instructores Externos</h3>
                                <div className="selected-info">
                                    Curso: <strong>{selectedCourse.title}</strong>
                                </div>

                                {/* CSV Email Input for Instructors */}
                                <div className="csv-input-section instructor">
                                    <h4>👨‍🏫 Asignar Instructor por Email</h4>
                                    <textarea
                                        placeholder="Ingresa emails de instructores separados por coma, punto y coma, o líneas nuevas. Ej:&#10;instructor1@email.com, instructor2@email.com&#10;instructor3@email.com"
                                        value={csvEmails}
                                        onChange={(e) => setCsvEmails(e.target.value)}
                                    />
                                    <small>Los instructores serán pre-asignados. Cuando se registren y se les asigne al grupo Instructores_Externos, verán el curso automáticamente.</small>
                                    {getCsvEmailCount() > 0 && (
                                        <div className="csv-count instructor">{getCsvEmailCount()} email(s) detectados</div>
                                    )}
                                </div>

                                {instructors.length > 0 && (
                                    <>
                                        <div className="divider"><span>o selecciona instructores registrados</span></div>

                                        <div className="items-list">
                                            {filteredInstructors.map(instructor => {
                                                const instructorId = instructor.email || instructor.username;
                                                const isAssigned = getAssignedUsers(selectedCourse.folder).includes(instructorId);
                                                const isSelected = selectedItems.includes(instructorId);

                                                return (
                                                    <div
                                                        key={instructorId}
                                                        className={`item-card instructor ${isSelected ? 'selected' : ''} ${isAssigned ? 'assigned' : ''}`}
                                                        onClick={() => !isAssigned && toggleSelection(instructorId)}
                                                    >
                                                        <div className="item-title">{instructor.email || instructor.username}</div>
                                                        <div className="item-subtitle">{instructor.name || 'Instructor Externo'}</div>
                                                        {isAssigned ? (
                                                            <button
                                                                className="remove-btn"
                                                                onClick={(e) => { e.stopPropagation(); handleRemoveAssignment(instructorId, selectedCourse.folder); }}
                                                            >
                                                                ✕ Quitar
                                                            </button>
                                                        ) : (
                                                            <input
                                                                type="checkbox"
                                                                checked={isSelected}
                                                                onChange={() => toggleSelection(instructorId)}
                                                                onClick={(e) => e.stopPropagation()}
                                                            />
                                                        )}
                                                    </div>
                                                );
                                            })}
                                        </div>
                                    </>
                                )}

                                {(selectedItems.length > 0 || getCsvEmailCount() > 0) && (
                                    <button className="assign-btn instructor" onClick={handleAssign}>
                                        ✓ Asignar {selectedItems.length + getCsvEmailCount()} instructor(es)
                                    </button>
                                )}
                            </div>
                        )}
                    </div>
                ) : (
                    <div className="assignment-flow">
                        <div className="selection-panel">
                            <h3>1. Selecciona un Estudiante</h3>
                            <input
                                type="text"
                                placeholder="Buscar usuarios..."
                                value={searchTerm}
                                onChange={(e) => setSearchTerm(e.target.value)}
                                className="search-input"
                            />
                            <div className="items-list">
                                {filteredUsers.map(user => {
                                    const userId = user.email || user.username;
                                    return (
                                        <div
                                            key={userId}
                                            className={`item-card ${selectedUser?.email === user.email ? 'selected' : ''}`}
                                            onClick={() => { setSelectedUser(user); setSelectedItems([]); }}
                                        >
                                            <div className="item-title">{user.email || user.username}</div>
                                            <div className="item-subtitle">{user.name || 'Sin nombre'}</div>
                                            <div className="item-badge">
                                                {getAssignedCourses(userId).length} cursos
                                            </div>
                                        </div>
                                    );
                                })}
                            </div>
                        </div>

                        {selectedUser && (
                            <div className="selection-panel">
                                <h3>2. Selecciona Cursos</h3>
                                <div className="selected-info">
                                    Estudiante: <strong>{selectedUser.email || selectedUser.username}</strong>
                                </div>
                                <div className="items-list">
                                    {courses.map(course => {
                                        const userId = selectedUser.email || selectedUser.username;
                                        const isAssigned = getAssignedCourses(userId).includes(course.folder);
                                        const isSelected = selectedItems.includes(course.folder);

                                        return (
                                            <div
                                                key={course.folder}
                                                className={`item-card ${isSelected ? 'selected' : ''} ${isAssigned ? 'assigned' : ''}`}
                                                onClick={() => !isAssigned && toggleSelection(course.folder)}
                                            >
                                                <div className="item-title">{course.title}</div>
                                                <div className="item-subtitle">{course.folder}</div>
                                                {isAssigned ? (
                                                    <button
                                                        className="remove-btn"
                                                        onClick={(e) => { e.stopPropagation(); handleRemoveAssignment(userId, course.folder); }}
                                                    >
                                                        ✕ Quitar
                                                    </button>
                                                ) : (
                                                    <input
                                                        type="checkbox"
                                                        checked={isSelected}
                                                        onChange={() => toggleSelection(course.folder)}
                                                        onClick={(e) => e.stopPropagation()}
                                                    />
                                                )}
                                            </div>
                                        );
                                    })}
                                </div>
                                {selectedItems.length > 0 && (
                                    <button className="assign-btn" onClick={handleAssign}>
                                        ✓ Asignar {selectedItems.length} curso(s)
                                    </button>
                                )}
                            </div>
                        )}
                    </div>
                )}
            </div>
        </div>
    );
}

export default AsignadorPortal;
