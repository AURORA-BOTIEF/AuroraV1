def estimate(text):
    w = 0
    for c in text:
        if c in 'ilI1tfj.,:;': w += 0.5
        elif c in 'mwMW': w += 1.5
        elif c.isupper(): w += 1.2
        else: w += 1.0
    return w

print("Características Técnicas de las Distribuciones:", estimate("Características Técnicas de las Distribuciones"))
print("Sistema de Archivos: Concepto Fundamental:", estimate("Sistema de Archivos: Concepto Fundamental"))
print("Aplicación Práctica: Elegir una Distribución:", estimate("Aplicación Práctica: Elegir una Distribución"))
