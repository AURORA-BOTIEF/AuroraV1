// src/components/ProfileModal.jsx
import './ProfileModal.css';
import defaultFoto from '../assets/default.jpg';
import { useState } from 'react';
import { fetchAuthSession } from 'aws-amplify/auth';
import { S3Client } from '@aws-sdk/client-s3';
import { Upload } from '@aws-sdk/lib-storage';

function ProfileModal({ token }) {
  const [visible, setVisible] = useState(false);
  const [nombre, setNombre] = useState('');
  const [email, setEmail] = useState('');
  const [foto, setFoto] = useState(defaultFoto);
  const [archivo, setArchivo] = useState(null);

  const BUCKET = import.meta.env.VITE_COURSE_BUCKET || 'crewai-course-artifacts';
  const AWS_REGION = import.meta.env.VITE_AWS_REGION || 'us-east-1';

  const handleFotoChange = (e) => {
    const file = e.target.files[0];
    if (!file) return;
    setArchivo(file);
    const reader = new FileReader();
    reader.onload = (e) => setFoto(e.target.result);
    reader.readAsDataURL(file);
  };

  const parseJwt = (token) => {
    const payload = token.split('.')[1];
    return JSON.parse(atob(payload));
  };

  const subirFotoAS3 = async () => {
    const userId = parseJwt(token).sub;
    const nombreArchivo = `profiles/${userId}.jpg`;

    // Use Amplify session credentials to upload directly to S3 with IAM auth
    const session = await fetchAuthSession();
    if (!session || !session.credentials) throw new Error('No se encontraron credenciales autenticadas');

    const s3Client = new S3Client({
      region: AWS_REGION,
      credentials: session.credentials,
    });

    const bucketName = BUCKET;
    const fileSize = archivo.size || 0;
    const MAX_SINGLE_PUT = 64 * 1024 * 1024; // 64MB

    const upload = new Upload({
      client: s3Client,
      params: {
        Bucket: bucketName,
        Key: nombreArchivo,
        Body: archivo,
        ContentType: archivo.type,
      },
      queueSize: 3,
      partSize: Math.min(MAX_SINGLE_PUT, Math.max(5 * 1024 * 1024, fileSize + 1)),
    });

    try {
      await upload.done();
    } catch (err) {
      console.warn('Profile upload failed, attempting PutObject fallback:', err && err.message);
      const msg = String(err && err.message || '').toLowerCase();
      if (msg.includes('crc32') || msg.includes('checksum')) {
        // Fallback to single PUT
        await s3Client.send(new PutObjectCommand({
          Bucket: bucketName,
          Key: nombreArchivo,
          Body: archivo,
          ContentType: archivo.type,
        }));
      } else {
        throw err;
      }
    }

    // Return the object URL (public URL assumes bucket/object ACL or CloudFront)
    return `https://${BUCKET}.s3.amazonaws.com/${nombreArchivo}`;
  };

  const guardarPerfil = async () => {
    try {
      const fotoUrl = archivo ? await subirFotoAS3() : foto;
      document.getElementById('fotoPerfilSidebar').src = fotoUrl;
      document.getElementById('nombreSidebar').textContent = nombre || 'Usuario';
      document.getElementById('emailSidebar').textContent = email || 'usuario@ejemplo.com';
      alert('✅ Perfil guardado correctamente');
      setVisible(false);
    } catch {
      alert('❌ Error al guardar perfil');
    }
  };

  return (
    <>
      <div id="modalPerfil" style={{ display: visible ? 'block' : 'none' }}>
        <h3>Mi perfil</h3>
        <div className="foto-container">
          <img id="previewFoto" src={foto} alt="Foto perfil" />
          <br />
          <input type="file" id="inputFoto" accept="image/*" onChange={handleFotoChange} />
        </div>
        <label>Nombre:</label>
        <input type="text" id="nombrePerfil" placeholder="Tu nombre" onChange={(e) => setNombre(e.target.value)} />
        <label>Email:</label>
        <input type="email" id="emailPerfil" placeholder="Correo electrónico" onChange={(e) => setEmail(e.target.value)} />
        <div className="botones">
          <button id="guardarPerfil" onClick={guardarPerfil}>💾 Guardar</button>
          <button id="cerrarPerfil" onClick={() => setVisible(false)}>❌</button>
        </div>
      </div>
      <img
        id="fotoPerfilSidebar"
        src={foto}
        alt="Foto perfil"
        onClick={() => setVisible(true)}
        style={{ display: 'none' }} // Se reemplaza por el que está en Sidebar
      />
    </>
  );
}

export default ProfileModal;
