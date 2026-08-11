# TMX Enterprise AI Reference Platform

## Manual de Usuario

---

### Portada

| | |
|---|---|
| **Nombre del proyecto** | TMX Enterprise AI Reference Platform (plataforma de referencia académica) |
| **Documento** | Manual de Usuario |
| **Versión** | 1.1 (PBI-10-06: actualizado tras la integración de Microsoft Entra ID) |
| **Fecha** | 2026-08-11 |
| **Autor** | Miguel Marin |

> **Nota:** Este es un proyecto de referencia académico. Toda póliza, siniestro, broker, cliente y comisión mencionados en este manual es **sintético** — el sistema no contiene datos reales de clientes ni de negocio.

---

## 1. Introducción

El TMX Enterprise AI Reference Platform es un asistente conversacional que ayuda a los usuarios
de negocio a resolver solicitudes relacionadas con seguros a través de una conversación en
lenguaje natural, en lugar de tener que navegar por varios formularios o sistemas distintos.

**¿Qué es el sistema?**

Es un asistente de chat al que el usuario le escribe lo que necesita, en español o en inglés, y
el propio asistente identifica automáticamente el área correspondiente (siniestros, servicios
para brokers, o nuevos negocios), solicita únicamente la información que aún falta, y completa la
solicitud.

**¿Para qué sirve?**

- Ofrece un único punto de entrada conversacional para tres áreas de negocio distintas — el
  usuario no necesita saber qué sistema o departamento atiende cada tipo de solicitud.
- Guía al usuario paso a paso, preguntando solo lo que realmente falta para completar el trámite.
- Genera cada respuesta a partir de las propias fuentes de información aprobadas de la
  plataforma — el asistente no inventa ni supone el estado de una póliza, un pago, una cobertura
  o una comisión; siempre lo consulta.

**¿Qué problemas resuelve?**

- Evita que el usuario tenga que repetir información ya proporcionada, incluso si cambia de tema
  dentro de la misma conversación (ver Escenario 5).
- Reduce la necesidad de conocer formularios o números de identificación internos — por ejemplo,
  basta con dar el nombre de un broker para que el sistema lo identifique.
- Guarda automáticamente cada conversación, de modo que el usuario puede retomarla más adelante.

---

## 2. ¿Quién debe utilizar este sistema?

| Perfil de usuario | Cómo utiliza la plataforma |
|---|---|
| **Personal de Siniestros** | Guía a quien reporta un siniestro, o utiliza el asistente para revisar qué información se requiere para registrar un aviso. |
| **Brokers** | Consulta el estado de pólizas o transacciones, y revisa o solicita el pago de sus propias comisiones. |
| **Área Comercial** | Registra una nueva solicitud de seguro comercial (un posible cliente de negocio) para su seguimiento interno. |
| **Usuarios internos** | Cualquier persona de la organización que necesite una respuesta rápida sobre una póliza, siniestro o comisión sintética, sin tener que acceder a un sistema interno independiente. |

Esta plataforma es una herramienta interna, orientada a fines demostrativos y académicos. No es
una aplicación de autoservicio dirigida al público general.

---

## 3. Acceso al sistema

Se accede a la plataforma desde un navegador web estándar, en la dirección proporcionada por el
responsable del proyecto o del área de sistemas. No requiere instalación alguna.

### 3.1 Iniciar sesión con Microsoft

La aplicación requiere iniciar sesión con una cuenta de Microsoft antes de poder utilizarse. Al
abrir la aplicación se muestra una pantalla de inicio de sesión — no la interfaz de conversación
— hasta que el inicio de sesión se completa.

1. Selecciona **"Iniciar sesión con Microsoft"**.
2. Se abre una ventana emergente de inicio de sesión de Microsoft.

*Figura 1a. Pantalla de inicio de sesión (botón "Iniciar sesión con Microsoft").*

### 3.2 Seleccionar cuenta

En la ventana emergente de Microsoft, elige la cuenta de Microsoft que deseas utilizar (o
escribe las credenciales de tu cuenta de Microsoft laboral, escolar o personal si el navegador
aún no recuerda ninguna). Esta pantalla la presenta directamente Microsoft — la aplicación nunca
solicita ni conoce tu contraseña. Una vez completado el inicio de sesión, la ventana emergente se
cierra automáticamente y se carga la interfaz de conversación.

*Figura 1b. Ventana emergente de selección de cuenta de Microsoft.*

### 3.3 Sesión autenticada

Una vez iniciada la sesión, el encabezado en la parte superior de la aplicación muestra el
nombre de tu cuenta y un indicador de estado de conexión. A partir de ese momento, cada
conversación queda asociada a tu identidad autenticada — no al navegador que estés utilizando
(ver Sección 3.5).

*Figura 1c. Encabezado con sesión iniciada, mostrando el nombre de la cuenta y el botón "Cerrar sesión".*

### 3.4 Expiración de la sesión

Tu sesión se mantiene activa automáticamente en segundo plano — la mayoría de las veces no
notarás que un token se está renovando. Si la sesión ha estado inactiva el tiempo suficiente
como para que ya no pueda renovarse automáticamente, la aplicación te pedirá iniciar sesión de
nuevo (una nueva ventana emergente de Microsoft) la próxima vez que necesite enviar una
solicitud. Basta con completar el inicio de sesión de nuevo como en las Secciones 3.1–3.2; tus
conversaciones anteriores no se pierden — vuelven a aparecer en el historial del panel lateral en
cuanto inicias sesión nuevamente (ver Sección 3.5).

### 3.5 Historial de conversaciones después de iniciar sesión

El historial de conversaciones está asociado a tu **identidad autenticada**, no al navegador ni
al dispositivo — un cambio respecto a versiones anteriores de esta plataforma. Iniciar sesión con
la misma cuenta de Microsoft desde un navegador o equipo distinto muestra el mismo historial de
conversaciones; iniciar sesión con una cuenta de Microsoft **diferente** muestra únicamente las
conversaciones de esa cuenta, nunca las de otro usuario. Esto lo garantiza la propia plataforma,
no solo la interfaz — consulta la documentación dirigida al administrador del sistema para el
detalle técnico.

### 3.6 Cerrar sesión

Selecciona **"Cerrar sesión"** en el encabezado para finalizar tu sesión. Serás dirigido de
vuelta a la pantalla de inicio de sesión (Sección 3.1). Cerrar sesión no elimina ninguna
conversación — al volver a iniciar sesión con la misma cuenta verás el mismo historial de
conversaciones de antes.

---

## 4. Descripción de la pantalla principal

La aplicación es una única pantalla de conversación, dividida en tres áreas visibles al mismo
tiempo. No existen otras pantallas o menús además de los descritos a continuación — esta sección
documenta únicamente lo que realmente está implementado.

### 4.1 Panel lateral (izquierda)

- **Botón "+ Nueva conversación"** — inicia una conversación completamente nueva. La conversación
  anterior no se elimina; permanece disponible en el historial.
- **Cuadro de búsqueda** — filtra el historial de conversaciones por título conforme se escribe.
- **Historial de conversaciones** — lista de todas las conversaciones previas de este navegador,
  con su título y la fecha/hora de la última actualización, de la más reciente a la más antigua.
  Al seleccionar una, se vuelve a cargar por completo en el área de conversación.
- **Ejemplos de mensajes** — una breve lista de mensajes ya redactados ("Siniestros", "Servicios a
  corredores", "Nuevos negocios", "Siniestros + Conocimiento"), cada uno preparado para dirigirse
  automáticamente al área correspondiente. Al seleccionar uno, se envía de inmediato.
- Una nota recordando que solo se utilizan datos sintéticos — ninguna póliza, siniestro o cliente
  es real.

*Figura 2. Panel lateral con historial de conversaciones y ejemplos de mensajes.*

### 4.2 Área de conversación (centro)

- **Área de respuestas** — muestra la conversación en curso, con los mensajes del usuario y las
  respuestas del asistente en orden.
- **Etiqueta del especialista** — cada respuesta del asistente que proviene de un área
  especializada se identifica con un nombre amigable: "Siniestros", "Servicios a Corredores",
  "Nuevos Negocios", o "Asistente" (utilizado cuando la solicitud no corresponde a un área
  específica). El usuario nunca ve un nombre técnico interno.
- **Referencias de fuentes** — cuando una respuesta se basa en los documentos de referencia de la
  plataforma (por ejemplo, al preguntar "¿qué documentos necesito para reportar un siniestro?"),
  la respuesta se marca como "Basado en N fuente(s)", junto con una breve lista numerada de
  referencias, de manera que el usuario pueda ver que la respuesta se apoya en un documento real y
  no fue inventada.
- **Indicador de escritura** — mientras el asistente prepara una respuesta, aparece brevemente el
  indicador "Analizando…".
- **Mensajes del sistema (errores)** — si un mensaje no puede enviarse (por ejemplo, por un
  problema de conexión), el asistente muestra un aviso genérico ("Lo sentimos, ocurrió un problema
  al conectar con el Asistente de TMX. Por favor intenta de nuevo.") junto con un botón
  "Reintentar" que vuelve a enviar el mismo mensaje. Nunca se muestra al usuario un detalle técnico
  del error.
- **Cuadro de entrada de mensaje** — donde el usuario escribe su mensaje.

*Figura 3. Conversación inicial en el área principal.*

### 4.3 Elementos que NO existen

Para evitar confusiones al comparar este manual con la aplicación real: no existe un panel de
control (dashboard), no existe pantalla de configuración, no existe control para adjuntar
archivos, no existe panel de administración, y no existe una pantalla independiente por cada área
especializada — toda la interacción ocurre en la única ventana de conversación descrita arriba.

---

## 5. Escenario 1 — Consultar el estado de una póliza

Este escenario utiliza la función de Servicios para Brokers para consultar si una póliza está
vigente y si los pagos están al corriente, usando la póliza sintética `SYN-POL-0002`.

**Conversación:**

| Turno | Quién | Mensaje |
|---|---|---|
| 1 | Usuario | Hola, quiero consultar información con mi corredor. |
| 1 | Asistente (Servicios a Corredores) | ¿En qué te puedo ayudar — consultar el estado de una póliza o transacción, o revisar tus comisiones? |
| 2 | Usuario | El estado de mi póliza. |
| 2 | Asistente | Por favor indica el número de póliza sintética. |
| 3 | Usuario | SYN-POL-0002 |
| 3 | Asistente | Estado de la póliza SYN-POL-0002: active. Esta póliza tiene un pago pendiente. |

*Figura 4. Consulta de póliza en Servicios a Corredores.*

**¿Qué debe hacer el usuario?**

1. Indicar que desea consultar información con su corredor (o mencionar directamente su póliza).
2. Si el asistente pregunta qué tipo de ayuda necesita, responder claramente: estado de póliza, de
   transacción, o comisiones.
3. Proporcionar el número de póliza sintética cuando se le solicite.
4. Leer la respuesta: el asistente siempre indica el estado de la póliza (`active`, `lapsed` o
   `cancelled`) y si los pagos están al corriente, como un hecho consultado — el asistente no
   modifica ni decide sobre la póliza, únicamente informa.

---

## 6. Escenario 2 — Reportar un siniestro

Este escenario muestra un reporte completo de siniestro utilizando la póliza sintética
`SYN-POL-0001` (una póliza de auto vigente, con pagos al corriente).

**Conversación:**

| Turno | Quién | Mensaje |
|---|---|---|
| 1 | Usuario | Necesito reportar un siniestro. |
| 1 | Asistente (Siniestros) | Claro. ¿A nombre de quién está la póliza? |
| 2 | Usuario | SYN-POL-0001 |
| 2 | Asistente | Cuéntame sobre el incidente: ¿qué día ocurrió (AAAA-MM-DD), dónde fue, y qué tipo de siniestro es (colisión, robo, incendio, daño por agua, clima, vandalismo, otro)? |
| 3 | Usuario | 2026-08-01 |
| 3 | Asistente | Hasta ahora tengo: ✔ póliza ✔ fecha. Solo me falta: ¿Dónde ocurrió el incidente? ¿Qué tipo de siniestro fue…? |
| 4 | Usuario | en mi casa |
| 4 | Asistente | Hasta ahora tengo: ✔ póliza ✔ fecha ✔ ubicación. Solo me falta: ¿Qué tipo de siniestro fue…? |
| 5 | Usuario | fue una colisión |
| 5 | Asistente | Hasta ahora tengo: ✔ póliza ✔ fecha ✔ ubicación ✔ tipo de siniestro. Solo me falta: ¿Podrías describir brevemente qué sucedió? |
| 6 | Usuario | Otro carro me golpeó estando estacionado. |
| 6 | Asistente | Solo me falta: ¿Cuál es el mejor teléfono para contactarte? |
| 7 | Usuario | 555-123-4567 |
| 7 | Asistente | Solo me falta: ¿Hubo personas lesionadas, y estuvieron involucrados terceros? (sí/no para cada una) |
| 8 | Usuario | No hubo personas lesionadas ni terceros involucrados. |
| 8 | Asistente | Solo me falta: ¿El vehículo todavía puede circular? |
| 9 | Usuario | Sí, el vehículo puede circular. |
| 9 | Asistente | Tu póliza está vigente. Los pagos de esta póliza están al corriente. Tu cobertura es 'Cobertura amplia', con suma asegurada de $250,000.00 y deducible de $5,000.00. Antes de registrar tu siniestro, confirmemos los datos: póliza SYN-POL-0001, incidente del 2026-08-01 en mi casa, tipo 'collision'. El vehículo puede circular. ¿Confirmas que deseamos registrar tu siniestro con esta información? (sí/no) |
| 10 | Usuario | Sí |
| 10 | Asistente | Tu aviso de siniestro ha sido registrado. Tu número de referencia es SYN-CLM-2026-0002. Synthetic Adjuster Okafor fue asignado a tu siniestro SYN-CLM-2026-0002 y te contactará pronto. |

*Figura 5. Reporte de siniestro paso a paso.*

**Explicación del flujo:**

1. **Validación de póliza** — el asistente solicita el número de póliza y, una vez reunidos todos
   los demás datos, valida su estado, el estado de pago y la cobertura, informándolos como hechos.
2. **Captura del incidente** — se pregunta, en una sola solicitud combinada, la fecha, el lugar y
   el tipo de siniestro; en cada turno posterior el asistente pregunta únicamente lo que aún falta
   — el usuario nunca necesita repetir lo ya proporcionado.
3. **Preguntas adicionales** — teléfono de contacto, si hubo personas lesionadas, si hubo terceros
   involucrados, y (para un siniestro de auto) si el vehículo todavía puede circular.
4. **Confirmación** — antes de registrar cualquier dato, el asistente resume toda la información
   recopilada y solicita una confirmación explícita (sí/no). Responder "no" no descarta la
   información capturada — el sistema pregunta qué dato se desea corregir.
5. **Número de referencia** — una vez confirmado, el asistente registra el siniestro y entrega un
   número de referencia con el formato `SYN-CLM-<año>-<consecutivo>` (el consecutivo exacto
   depende de cuántos siniestros se hayan registrado previamente en la sesión), además del nombre
   del ajustador sintético asignado para dar seguimiento. El ajustador asignado también puede
   variar entre ejecuciones, ya que depende del número de referencia exacto obtenido.

> **Nota:** conforme al diseño de la plataforma, el asistente únicamente registra los hechos
> reportados — nunca aprueba, rechaza ni determina la cobertura de un siniestro. La decisión final
> siempre corresponde a una persona.

> **Nota:** algunos valores internos (por ejemplo, el estado de la póliza o el tipo de siniestro
> dentro del resumen de confirmación) pueden aparecer en inglés dentro de la respuesta en
> español — como se observa en el ejemplo anterior ("active", "collision"). Esto corresponde al
> comportamiento real de la plataforma en esta versión, no a un error de este manual.

---

## 7. Escenario 3 — Consultar Servicios para Brokers

Este escenario muestra una consulta de comisiones y una solicitud de pago, utilizando el broker
sintético `Synthetic Brokerage One` (ID de broker `SYN-BRK-0001`).

**Conversación:**

| Turno | Quién | Mensaje |
|---|---|---|
| 1 | Usuario | Hola, quiero conocer mis comisiones. |
| 1 | Asistente (Servicios a Corredores) | ¿Con qué broker trabajas, y qué período te gustaría revisar? |
| 2 | Usuario | Soy Synthetic Brokerage One, período 2026-Q1. |
| 2 | Asistente | Comisión de 2026-Q1: $1,250.00 (estado: available). ¿Te gustaría solicitar el pago de esta comisión? (sí/no) |
| 3 | Usuario | Sí, por favor. |
| 3 | Asistente | Tu solicitud de pago de comisión ha sido registrada. Referencia: SYN-PAYREQ-2026-0002. |

*Figura 6. Consulta de comisiones y solicitud de pago.*

**Explicación del flujo:**

- **Consulta de comisiones** — el asistente solicita, en una sola pregunta, el nombre del broker y
  el período a revisar (un ID de broker escrito directamente también funciona, y omite el paso de
  búsqueda por nombre).
- **Identificación del broker** — el nombre del broker se relaciona automáticamente con la cuenta
  correspondiente; el usuario nunca necesita conocer o escribir un ID interno.
- **Consulta de pólizas** — la misma área de Servicios a Corredores también atiende "¿cuál es el
  estado de la póliza X?" (Escenario 1) y "¿cuál es el estado de la transacción X?" — el asistente
  pregunta qué tipo de ayuda se requiere si no queda claro en el primer mensaje.
- **Monto y estado de la comisión** — se informa como un hecho (`available`, `pending` o `paid`).
  Solo una comisión marcada como `available` puede solicitarse para pago; en cualquier otro caso,
  el asistente no ofrecerá esa opción.
- **Solicitud de pago de comisión** — si se confirma, se entrega un número de referencia con el
  formato `SYN-PAYREQ-<año>-<consecutivo>`.

---

## 8. Escenario 4 — Registrar un Nuevo Negocio

Este escenario muestra el flujo completo del área de Nuevos Negocios: la captura de la
información necesaria para registrar una nueva solicitud comercial para su seguimiento interno.

**Conversación:**

| Turno | Quién | Mensaje |
|---|---|---|
| 1 | Usuario | Necesito una cotización para asegurar mi empresa. |
| 1 | Asistente (Nuevos Negocios) | ¿Cuál es el nombre de tu empresa o negocio? |
| 2 | Usuario | Constructora Sintética del Norte |
| 2 | Asistente | ¿Cuál es el nombre completo de la persona de contacto? |
| 3 | Usuario | María Fernanda López |
| 3 | Asistente | ¿Prefieres que te contactemos por correo electrónico o por teléfono? |
| 4 | Usuario | Por correo electrónico. |
| 4 | Asistente | ¿Cuál es el mejor correo electrónico para contactarte? |
| 5 | Usuario | maria.lopez@example.com |
| 5 | Asistente | ¿Qué tipo de seguro o cobertura estás buscando? |
| 6 | Usuario | Seguro de responsabilidad civil para construcción. |
| 6 | Asistente | ¿Podrías describir brevemente tu negocio o el riesgo que te gustaría cubrir? |
| 7 | Usuario | Somos una constructora mediana, con unos 40 empleados, y manejamos proyectos residenciales. |
| 7 | Asistente | Gracias — tu solicitud ha sido registrada. Tu número de referencia es SYN-LEAD-2026-0002. Un representante te contactará por correo electrónico. |

*Figura 7. Registro de nuevo negocio paso a paso.*

**Explicación de cada paso:**

1. **Nombre de la empresa** — nombre del negocio que solicita el seguro.
2. **Persona de contacto** — nombre completo de la persona con quien dar seguimiento.
3. **Canal de contacto preferido** — correo electrónico o teléfono; el asistente solicita
   únicamente el dato correspondiente (el correo o el teléfono, según lo indicado).
4. **Necesidad de seguro** — el tipo de cobertura que se busca.
5. **Descripción del riesgo** — una breve descripción del negocio o del riesgo a cubrir.
6. **Registro** — una vez reunidos todos los datos, el asistente registra la solicitud y entrega
   un número de referencia con el formato `SYN-LEAD-<año>-<consecutivo>`, confirmando además el
   canal por el cual se dará seguimiento.

> **Importante:** conforme al diseño de la plataforma, este paso **nunca** genera una cotización,
> una prima ni una garantía de aceptación de cobertura — aun cuando el mensaje inicial del usuario
> solicite una "cotización". La función del asistente aquí se limita a recopilar información y
> registrar la solicitud, para que un asesor comercial humano dé seguimiento posteriormente.

---

## 9. Escenario 5 — Cambio de contexto durante la conversación

Este escenario muestra cómo el asistente conserva los datos relevantes al cambiar de área dentro
de la misma conversación, de manera que el usuario no tenga que repetir información ya
proporcionada.

**Punto de partida:** el usuario inicia reportando un siniestro, identificándose solo por su
nombre — sin escribir directamente un número de póliza:

| Turno | Quién | Mensaje |
|---|---|---|
| 1 | Usuario | Necesito reportar un siniestro. |
| 1 | Asistente (Siniestros) | Claro. ¿A nombre de quién está la póliza? |
| 2 | Usuario | Juan Pérez |
| 2 | Asistente | Encontré estas pólizas a tu nombre: la primera (Nissan Sentra 2022); la segunda (Toyota Hilux 2021). ¿Cuál corresponde a tu siniestro? |
| 3 | Usuario | SYN-POL-1001 |
| 3 | Asistente | Hasta ahora tengo: ✔ cliente ✔ póliza. Solo me falta: Cuéntame sobre el incidente: ¿qué día ocurrió (AAAA-MM-DD), dónde fue, y qué tipo de siniestro es…? |

> **Nota:** cuando el sistema encuentra más de una póliza a nombre de la persona, las describe
> brevemente (por ejemplo, por el vehículo) y pregunta cuál corresponde — el usuario nunca
> necesita memorizar un número de póliza si prefiere identificarse solo por su nombre.

En este punto, la plataforma ya conoce internamente tanto el **nombre del cliente** ("Juan
Pérez") como la **póliza** (`SYN-POL-1001`) para el resto de la conversación.

**De Siniestros a Servicios a Corredores:**

| Turno | Quién | Mensaje |
|---|---|---|
| 4 | Usuario | Ahora quiero consultar el estado de esa póliza con mi corredor. |
| 4 | Asistente (Servicios a Corredores) | Estado de la póliza SYN-POL-1001: active. Los pagos de esta póliza están al corriente. |

Nótese que el asistente cambió al área de Servicios a Corredores y respondió de inmediato — **no
volvió a solicitar el número de póliza**, porque ya había quedado establecido antes, mientras se
reportaba el siniestro.

**De Servicios a Corredores a Nuevos Negocios:**

Continuando la misma conversación, el usuario pregunta ahora sobre una nueva oportunidad de
negocio:

| Turno | Quién | Mensaje |
|---|---|---|
| 5 | Usuario | También quisiera una cotización para asegurar otro negocio que tengo. |
| 5 | Asistente (Nuevos Negocios) | ¿Cuál es el nombre de tu empresa o negocio? |
| 6 | Usuario | Constructora Sintética del Norte |
| 6 | Asistente | ¿Prefieres que te contactemos por correo electrónico o por teléfono? |

Nótese que el asistente preguntó por el **nombre de la empresa** (un dato genuinamente nuevo),
pero pasó directamente a preguntar por el **canal de contacto preferido** — no volvió a preguntar
"¿cuál es el nombre completo de la persona de contacto?", porque ese dato (el nombre del cliente,
establecido en el primer turno de la conversación) ya era conocido.

*Figura 8. Cambio de contexto entre Siniestros, Servicios a Corredores y Nuevos Negocios.*

**¿Qué observa el usuario?**

Cambiar de tema se siente como hablar con un mismo asistente que recuerda la conversación, y no
con tres sistemas distintos. Solo los datos que la plataforma efectivamente conserva (por ahora:
nombre del cliente o contacto, identidad del broker, número de póliza, número de siniestro,
nombre del negocio, fecha/tipo/lugar del incidente, y cobertura) se reutilizan automáticamente al
cambiar de tema — cualquier otro dato (por ejemplo, un número telefónico proporcionado a un área)
puede volver a solicitarse en un área distinta.

> **Nota de verificación:** este comportamiento depende de *cómo* se proporciona cada dato. Si en
> el primer paso el usuario hubiera escrito directamente un número de póliza (por ejemplo,
> "SYN-POL-0001") en lugar de su nombre, el sistema habría reconocido la póliza pero no un nombre
> de cliente — y en ese caso, el área de Nuevos Negocios sí volvería a preguntar por el nombre de
> la persona de contacto, ya que ese dato en particular no se habría establecido antes. La
> reutilización automática de información opera dato por dato, no por tema general de
> conversación.

---

## 10. Preguntas Frecuentes

**¿Por qué me solicita el número de póliza?**
El número de póliza es lo que permite al asistente consultar el estado real de tu póliza, el
estado de pago y la cobertura en los registros de la plataforma — sin ese número no es posible
confirmar ninguno de esos datos.

**¿Por qué hace preguntas adicionales?**
Cada área especializada necesita un conjunto específico y fijo de datos para completar la
solicitud (por ejemplo, un siniestro requiere la fecha, el lugar y el tipo de incidente). El
asistente pregunta únicamente lo que aún falta, un dato a la vez, en lugar de solicitar un
formulario extenso desde el inicio.

**¿Qué sucede si ingreso información incorrecta?**
Si un número de póliza, transacción o broker no se encuentra, el asistente lo indica directamente
(por ejemplo: "No encontramos una póliza con el número '...'. ¿Puedes verificarlo y
proporcionarlo de nuevo?") y solicita verificarlo y volver a proporcionarlo. El resto de la
información ya capturada no se pierde ni es necesario volver a ingresarla.

**¿Puedo cambiar de tema durante la conversación?**
Sí. Es posible pasar libremente entre siniestros, servicios a corredores y nuevos negocios dentro
de la misma conversación, y el asistente dirige automáticamente cada mensaje al área
correspondiente. Los datos ya establecidos se reutilizan cuando es posible (ver Escenario 5).

**¿Cómo reinicio la conversación?**
Selecciona "+ Nueva conversación" en el panel lateral. Esto inicia una conversación nueva; la
conversación anterior no se elimina y permanece disponible en el historial.

**¿Puedo adjuntar un documento (por ejemplo, una fotografía del daño)?**
No, en esta versión de la plataforma no existe ningún control para adjuntar archivos o
documentos.

**¿El asistente decide finalmente sobre mi siniestro o cotización?**
No. El asistente únicamente recopila y registra información — nunca aprueba ni rechaza un
siniestro, determina la cobertura, ni emite una cotización o prima. Esas decisiones siempre las
toma una persona.

---

## 11. Recomendaciones de uso

- **Proporcionar información completa cuando sea posible** — un mensaje que responde más de una
  pregunta a la vez (por ejemplo, indicar el broker y el período de comisión juntos) se interpreta
  correctamente y agiliza la conversación.
- **Responder directamente las preguntas del asistente** — cuando falta información, el asistente
  pregunta un dato a la vez; una respuesta directa mantiene fluida la conversación.
- **Utilizar el número correcto de póliza, broker o transacción** cuando se tenga a la mano — esto
  permite al asistente confirmar los datos de inmediato, en lugar de pedir que se verifiquen y
  reintenten.
- **Revisar la confirmación antes de registrar un trámite** — para un siniestro, el asistente
  siempre resume todo lo capturado y solicita una confirmación explícita antes de registrar
  cualquier dato; conviene revisarla con cuidado y responder "no" si algo debe corregirse.
- **Mantener temas relacionados en una misma conversación** — cambiar entre siniestros, servicios
  a corredores y nuevos negocios dentro de la misma conversación permite que el asistente
  reutilice los datos que ya conoce (Escenario 5); iniciar una conversación nueva para un tema no
  relacionado implica comenzar desde cero.

---

## 12. Limitaciones actuales

Se documentan únicamente las limitaciones que realmente existen en esta versión de la plataforma.

- **Se requiere una cuenta de Microsoft.** No existe acceso anónimo ni de invitado — toda
  utilización de la aplicación requiere iniciar sesión con Microsoft (ver Sección 3).
- **Solo se utilizan datos sintéticos.** Toda póliza, siniestro, broker, cliente y comisión que
  menciona el asistente es ficticia, con fines demostrativos — no existe conexión con ningún
  sistema de negocio real ni con datos reales de clientes.
- **No es posible adjuntar documentos o archivos.** La interfaz no cuenta con ninguna función para
  adjuntar una fotografía, un PDF u otro archivo a la conversación.
- **Nunca se genera una cotización, prima o decisión de cobertura.** El área de Nuevos Negocios
  únicamente registra una solicitud para seguimiento humano; el área de Siniestros únicamente
  registra hechos, nunca una determinación de cobertura.
- **La memoria conserva solamente ciertos datos específicos.** Como se muestra en el Escenario 5,
  solo un conjunto fijo de datos (nombre del cliente o contacto, identidad del broker, número de
  póliza, número de siniestro, nombre del negocio, fecha/tipo/lugar del incidente y cobertura) se
  reutiliza automáticamente entre distintos temas de una misma conversación — cualquier otro dato
  puede volver a solicitarse en un área distinta.
- **No es posible eliminar ni renombrar una conversación** desde la interfaz — solo se puede
  iniciar una nueva ("+ Nueva conversación") o volver a abrir una existente desde el historial.
- **La interfaz se presenta en español de forma predeterminada** (mensaje de bienvenida, ejemplos
  de mensajes y etiquetas del panel lateral). El asistente sí comprende y puede responder también
  en inglés, aunque los elementos visibles de la interfaz están orientados principalmente al
  español.

---

## 13. Solución de problemas

| Problema | Posible causa | Qué debe hacer el usuario |
|---|---|---|
| El asistente respondió de forma general, sin dirigirme al área correcta | El mensaje no contenía una palabra que el asistente reconozca para un área específica (siniestros, servicios a corredores o nuevos negocios) | Redactar el mensaje usando un término más directo sobre lo que se necesita, por ejemplo: "reportar un siniestro", "mis comisiones" o "cotización para mi empresa" |
| Apareció un mensaje indicando un problema de conexión, con un botón "Reintentar" | Ocurrió un problema temporal de conectividad al enviar el mensaje | Seleccionar "Reintentar" para reenviar el mismo mensaje; si el problema continúa, intentarlo de nuevo en unos minutos |
| El asistente volvió a pedirme el número de póliza, broker o transacción después de haberlo proporcionado | El número proporcionado no se encontró en los registros sintéticos de la plataforma, por lo que el asistente solicita verificarlo y volver a ingresarlo | Verificar el número y proporcionarlo nuevamente tal como fue emitido (por ejemplo, `SYN-POL-0001`) |
| Cambié de tema y el asistente volvió a preguntarme algo que ya había respondido | Ese dato en particular no forma parte del conjunto de información que la plataforma reutiliza automáticamente entre temas (ver Sección 12) | Proporcionar nuevamente el dato solicitado — este comportamiento es esperado, no un error |
| No veo una conversación anterior en el historial | Es posible que la sesión esté iniciada con una cuenta de Microsoft distinta a la utilizada para crear esa conversación | El historial de conversaciones está asociado a la cuenta de Microsoft con la que se inició sesión, no al navegador (ver Sección 3.5) — verifica que sea la misma cuenta, cerrando sesión y volviendo a iniciarla si es necesario |
| La ventana emergente de inicio de sesión no apareció, o se cerró sin completarse | Es posible que el navegador haya bloqueado la ventana emergente, o que el inicio de sesión se haya cancelado | Permitir ventanas emergentes para este sitio e intentar "Iniciar sesión con Microsoft" nuevamente |
| Se me pidió iniciar sesión de nuevo en medio del uso de la aplicación | La sesión había estado inactiva el tiempo suficiente como para que ya no pudiera renovarse automáticamente (ver Sección 3.4) | Inicia sesión nuevamente; tus conversaciones anteriores no se pierden y vuelven a aparecer al iniciar sesión |
| El número de referencia del siniestro/solicitud que recibí es distinto al de un ejemplo de este manual | Los números de referencia incluyen un consecutivo que aumenta con cada nuevo registro | Esto es normal — el número exacto puede variar; lo importante es que el formato (por ejemplo, `SYN-CLM-2026-000x`) sea el correcto |

---

## 14. Guía rápida

*(Esta página está diseñada para poder imprimirse de manera independiente.)*

### TMX Enterprise AI Reference Platform — Guía rápida

**¿Qué hace el sistema?** Un asistente de conversación para solicitudes sintéticas de Siniestros,
Servicios a Corredores y Nuevos Negocios — sin formularios, sin sistemas separados.

**Funciones principales**

| Área | Qué se puede solicitar |
|---|---|
| Siniestros | Reportar un siniestro; consultar póliza/pago/cobertura como parte de ese proceso |
| Servicios a Corredores | Consultar el estado de una póliza o transacción; revisar o solicitar el pago de comisiones |
| Nuevos Negocios | Registrar una nueva solicitud de seguro comercial para seguimiento |

**Acciones más comunes**

- Iniciar sesión con "Iniciar sesión con Microsoft" la primera vez que se abre la aplicación.
- Escribir la solicitud en español o inglés, con lenguaje natural — no se requieren comandos
  especiales.
- Responder una a una las preguntas del asistente.
- Seleccionar "+ Nueva conversación" para comenzar de nuevo.
- Seleccionar cualquier conversación del historial para reabrirla.
- Seleccionar "Reintentar" si un mensaje no se envía correctamente.
- Seleccionar "Cerrar sesión" para salir de la aplicación.

**Flujo típico de uso**

1. Describir con tus propias palabras lo que necesitas.
2. El asistente identifica el área correspondiente y solicita, uno a uno, los datos que faltan.
3. Para un siniestro: revisar el resumen y confirmar (sí/no) antes de que se registre.
4. Recibir un número de referencia (siniestro, solicitud de pago o nuevo negocio), según
   corresponda.

**Recomendaciones**

- Tener a la mano el número de póliza, el nombre o ID del broker, o la referencia de transacción,
  cuando aplique.
- Es posible cambiar de tema dentro de la misma conversación — los datos relevantes se recuerdan.
- No se utilizan datos reales — esta plataforma trabaja únicamente con pólizas, siniestros y
  clientes sintéticos.

---

## Referencias cruzadas

Este manual no repite intencionalmente el contenido técnico de despliegue ni de administración.
Para esos temas, consulte:

- `Deployment_Guide.md` — infraestructura y proceso de despliegue (audiencia técnica/TI).
- `Administrator_Guide.md` — operación diaria, monitoreo y solución de problemas técnicos
  (audiencia técnica/TI).
