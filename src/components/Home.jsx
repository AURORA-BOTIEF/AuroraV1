// src/components/Home.jsx
function Home() {
  return (
    <div
      style={{
        paddingLeft: '10cm', // espacio del sidebar
        minHeight: '100vh',
        backgroundColor: '#f5f9ff',
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
        fontFamily: 'Segoe UI, Tahoma, sans-serif',
      }}
    >
      <div style={{ textAlign: 'center' }}>
        <h1 style={{ fontSize: '2.5em', color: '#1b5784' }}>Bienvenido a THOR</h1>
        <p style={{ fontSize: '1.2em', color: '#333', marginTop: '10px' }}>
          Comienza tu experiencia educativa interactiva con IA.<br />
          Usa la barra lateral para acceder a las opciones.
        </p>
      </div>
    </div>
  );
}

export default Home;
