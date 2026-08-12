# Guía de Narración — Defensa Final del Proyecto

TMX Enterprise AI Multi-Agent Platform — guía de narración completa para las 12 diapositivas de `Final_Project_Presentation.pptx`. Cada sección corresponde a una diapositiva y está pensada para 60–90 segundos de exposición oral.

Duración objetivo total: 12–15 minutos, incluyendo la demostración en vivo referenciada en la narración de las diapositivas de arquitectura y resultados.

---


> **Nota de esta actualización (PBI-10-10):** esta guía refleja las 12 diapositivas generadas originalmente más la nueva Diapositiva 5 (“Patrones de IA Agéntica”). El archivo `.pptx` actual tiene diapositivas adicionales agregadas manualmente en PowerPoint (por ejemplo, una diapositiva de “Demostración en Vivo”) que no tienen todavía su narración correspondiente en este documento — no se inventó contenido para ellas.

---

## Diapositiva 1 — Portada

Buenos días. Voy a presentar TMX Enterprise AI Multi-Agent Platform, mi proyecto final, desde la
perspectiva de un arquitecto de soluciones: no solo qué se construyó, sino por qué cada decisión
arquitectónica se tomó así y qué alternativas se evaluaron y descartaron.

Es una implementación de referencia académica: usa datos sintéticos y APIs de negocio simuladas,
y explícitamente no representa una arquitectura de producción oficialmente aprobada por ninguna
organización real. Esa distinción es importante porque va a aparecer varias veces durante la
presentación: voy a separar siempre lo que está implementado y probado hoy de lo que es
arquitectura objetivo para un escenario de producción real.

---

## Diapositiva 2 — Problema de Negocio

La pregunta arquitectónica de fondo en esta diapositiva es: ¿por qué estos procesos están
fragmentados en primer lugar? No es un descuido operativo — cada proceso de seguros (siniestros,
servicios a corredores, nuevos negocios) se especializó con su propio conocimiento de dominio, y
esa especialización tiene valor real. El problema no es la especialización interna; es que esa
fragmentación se traslada tal cual al usuario, obligándolo a saber de antemano a qué área dirigirse.

La alternativa obvia —fusionar los tres procesos en un solo sistema monolítico— se descartó
implícitamente por ser costosa y riesgosa: reescribir la lógica de negocio de tres dominios para
unificarlos no es proporcional al problema real, que es de experiencia de usuario, no de lógica de
negocio. Una arquitectura multiagente resuelve exactamente esa asimetría: cada agente conserva la
especialización de su dominio, y un supervisor común resuelve la fragmentación únicamente en la
capa de experiencia, sin tocar los sistemas subyacentes. Esa es la justificación arquitectónica del
patrón, no solo una elección de moda por usar IA generativa.

Noten que deliberadamente no hablé de KPIs técnicos, de Azure, ni de autenticación en esta
diapositiva — eso viene después. Esta diapositiva responde una sola pregunta: ¿por qué vale la pena
resolver este problema con este patrón?

---

## Diapositiva 3 — Principios Arquitectónicos

Antes de mostrar el diagrama completo, quiero dejar explícitos los principios que guían cada
decisión de diseño — porque todo lo que van a ver en la diapositiva siguiente es una consecuencia
directa de estos seis principios, no decisiones aisladas.

API First y separación de dominios responden a la misma preocupación que la diapositiva anterior:
mantener los dominios de negocio independientes entre sí. Tool Calling determinista es
probablemente el principio más importante del proyecto: el modelo de lenguaje interpreta lenguaje
natural, pero jamás ejecuta una acción de negocio por sí mismo — solo puede solicitar una
herramienta, y una capa determinista decide si esa solicitud es válida y la ejecuta. Esto es lo
que hace que el sistema sea auditable: cada acción de negocio tiene un registro determinista, no
una inferencia probabilística.

El acoplamiento débil mediante interfaces (Protocols en Python) es lo que permitió, por ejemplo,
agregar autenticación empresarial completa sin reescribir la lógica de negocio, o diseñar la capa
serverless sin comprometer el resto del sistema mientras no está desplegada — ambos casos los van
a ver más adelante. Seguridad por diseño significa que la identidad se valida una sola vez, en el
borde del sistema, y todo lo interno confía en esa validación — nunca se revalida ni se asume en
capas internas. Y Cloud Native es la razón por la que no hay servidores que administrar manualmente
en ningún punto de la arquitectura.

---

## Diapositiva 4 — Arquitectura Empresarial Completa

Esta es la diapositiva central de toda la defensa, así que voy a recorrerla de arriba hacia abajo
explicando el porqué de cada capa, no solo qué hace.

El flujo empieza con el usuario autenticándose contra Microsoft Entra ID mediante OAuth2
Authorization Code con PKCE — el flujo recomendado para una aplicación pública como esta SPA, que
no puede guardar un secreto de cliente de forma segura. Cada solicitud subsiguiente llega a FastAPI
con un token, y FastAPI lo valida completo — firma, expiración, audiencia y emisor — contra las
claves públicas publicadas por Entra ID (JWKS). Ningún componente posterior vuelve a preguntar
quién es el usuario: esa es la esencia de seguridad por diseño que mencioné en la diapositiva
anterior.

El Supervisor Agent enruta de forma determinista —no probabilística— hacia uno de los tres agentes
de dominio, y cada agente accede a la lógica de negocio exclusivamente a través de la capa de
herramientas determinista, nunca directamente. Aquí quiero ser explícito con algo importante: el
recuadro de Azure Functions y Durable Functions tiene borde punteado y dice "arquitectura
objetivo" porque **no está desplegado hoy**. La capa de herramientas sí está completamente
diseñada, codificada y probada para ejecutarse ahí — pero el runtime actual, marcado en verde sólido,
es "Tool Provider en proceso": las mismas herramientas, la misma lógica de negocio, ejecutando
dentro del propio proceso de la API en lugar de en un endpoint serverless separado. Más adelante
explico por qué exactamente.

A la derecha están los servicios de IA y datos: Azure OpenAI para el razonamiento del modelo,
Cosmos DB para el historial de conversación, y Azure AI Search —marcado en ámbar porque está
provisionado pero su índice aún no está poblado, tema que profundizo en la diapositiva de
arquitectura del conocimiento. Abajo, en la franja transversal, están los servicios de plataforma
que no pertenecen a un paso específico del flujo sino que sostienen a todos: Container Apps y
Container Registry para el despliegue, Key Vault y Managed Identity para la gestión de secretos e
identidad de servicio, y Application Insights junto con Azure Monitor para observabilidad — los
detallo en las siguientes diapositivas.

---

## Diapositiva 5 — Patrones de IA Agéntica

Esta diapositiva cambió de fondo desde la versión anterior de esta defensa, y quiero
explicar exactamente qué cambió y por qué.

Anteriormente presentaba ReAct como una evolución futura. Un análisis dedicado de brechas contra
el requisito del curso —ReAct más Tool Calling como patrón primario— encontró que el mecanismo ya
existía: ToolCallingOrchestrator ya implementaba un bucle acotado de Razonar, Actuar, Observar,
Razonar de nuevo, con quince pruebas que ya lo confirmaban. Lo que faltaba no era construir algo
nuevo: faltaba generalizarlo —estaba conectado solo al agente de Siniestros— y nombrarlo
explícitamente como lo que es.

Por eso hoy ReAct más Tool Calling es el patrón primario, implementado en los tres agentes
especialistas: Claims, Broker Services y Commercial Intake. Cada uno razona internamente antes de
responder, decide si necesita una herramienta, la invoca, observa el resultado, y repite ese ciclo
solo lo necesario antes de dar su respuesta final. El Supervisor, en cambio, permanece
completamente fuera de ese bucle: sigue enrutando de forma determinista, por palabras clave, sin
ningún modelo de lenguaje involucrado — esa separación es intencional y está documentada en el
ADR-0011: el enrutamiento es una decisión de gobierno que debe ser reproducible; el razonamiento
sobre qué herramienta usar es responsabilidad de cada agente especialista.

Los patrones complementarios que ya estaban implementados —Multi-Agent, Planner-Executor, Memory,
Guardrails— siguen ahí, sin cambios; ReAct los complementa, no los reemplaza. Lo que sí cambió es
la lista de evolución futura: ya no incluye ReAct, porque dejó de ser futuro. Lo que queda son dos
patrones genuinamente no implementados — LLM-as-a-Judge y Self-Reflection — que evaluarían o
corregirían el propio razonamiento del agente, algo que este sistema no hace hoy.

Y quiero cerrar con la regla que no cambió en absoluto: el razonamiento interno de ese bucle nunca
se expone al usuario ni se guarda en el historial de conversación — solo la respuesta final. Eso
está comprobado con pruebas dedicadas, no solo diseñado.

---

## Diapositiva 6 — Decisiones de Arquitectura

Esta tabla es, en mi opinión, la diapositiva más importante para una defensa de arquitectura,
porque cada fila responde explícitamente "por qué esto y no lo otro", que es la pregunta que un
arquitecto de soluciones debe poder responder para cada tecnología incluida.

Quiero detenerme en dos decisiones porque generan la mayoría de las preguntas. Primero,
gpt-5-mini: no lo elegí porque los modelos más grandes sean innecesarios de forma general — los
elegí evaluando qué tareas realmente hace el modelo en este sistema. El modelo interpreta lenguaje
natural, mantiene el hilo de la conversación, detecta la intención del usuario y decide qué
herramienta invocar. No calcula primas, no decide coberturas, no autoriza pagos — eso lo hace
código determinista, como vimos en la diapositiva de principios. Para ese conjunto de tareas,
gpt-5-mini ofrece el mejor equilibrio entre latencia —crítica en una conversación interactiva— y
costo por token, sin sacrificar la calidad de conversación necesaria.

Segundo, Container Apps frente a AKS: esta es una decisión de complejidad operativa proporcional
al problema. TMX no tiene hoy una concurrencia de usuarios que justifique operar un clúster de
Kubernetes completo —con su propio plano de control, sus políticas de red, su gestión de nodos.
Container Apps da exactamente lo que se necesita hoy —contenedores administrados, autoescalado
declarativo, portabilidad Docker— sin ese costo operativo adicional. Es una decisión reversible: si
la carga de trabajo creciera de forma significativa, migrar a AKS es una evolución natural, no una
reescritura, porque ambos parten del mismo artefacto: una imagen Docker.

Las demás filas de la tabla siguen el mismo patrón de razonamiento: Cosmos DB porque el dato es
naturalmente un documento, Entra ID porque no tiene sentido reinventar autenticación cuando existe
un estándar empresarial auditado, Tool Calling determinista porque la auditabilidad de las
acciones de negocio no es negociable, Azure AI Search porque una cita verificable vale más que la
memoria implícita de un modelo, y Key Vault porque ningún secreto debe vivir en texto plano.

---

## Diapositiva 7 — Seguridad Empresarial

Todos estos controles responden a la misma pregunta de diseño: ¿en qué punto del sistema confiamos
y por qué? La respuesta arquitectónica es: se confía únicamente en un token validado en el borde
del sistema, y en nada más.

Entra ID reemplaza cualquier necesidad de mantener una base de usuarios y contraseñas propia — es
una decisión de reducir superficie de riesgo, no solo de conveniencia. PKCE existe porque esta es
una aplicación de página única: no puede guardar un secreto de cliente de forma segura en el
navegador, así que el flujo de autorización usa un desafío criptográfico generado localmente en
lugar de un secreto estático. La validación JWT completa —firma, expiración, audiencia y emisor— es
lo que separa "el cliente envió un token" de "el cliente envió un token válido para este sistema
específico, todavía vigente, con una firma auténtica": son verificaciones independientes, y las
cuatro son necesarias.

La mitigación de IDOR merece mención especial porque fue el hallazgo más importante de todo el
proceso de revisión de arquitectura de este proyecto: antes de esta implementación, el identificador
de usuario lo enviaba el propio cliente, lo que en principio permitía a un usuario leer las
conversaciones de otro si suponía o adivinaba su identificador. La corrección no fue solo agregar
autenticación —fue eliminar por completo la posibilidad de que la identidad provenga de un valor
enviado por el cliente. Y finalmente, Key Vault y Managed Identity resuelven el mismo problema desde
el lado de los servicios: ningún servicio de Azure se autentica con una clave que alguien tuvo que
copiar y pegar en una variable de entorno — la identidad administrada elimina esa credencial por
completo.

---

## Diapositiva 8 — Observabilidad y Operación

Quiero ser particularmente honesto en esta diapositiva, porque es fácil listar capacidades de
observabilidad como si todas estuvieran igualmente maduras, y no es el caso.

Lo que sí puedo afirmar con evidencia: cada solicitud genera un identificador de correlación que se
propaga a través de todo el sistema —Supervisor, Agente, herramienta— y aparece en cada línea de log
estructurado en formato JSON. Verifiqué esto directamente durante el desarrollo: es real y
funciona. Existen también tres alertas activas de Azure Monitor sobre tasa de error, latencia y
disponibilidad, confirmadas contra los nombres de métrica reales del recurso desplegado, no
inventadas.

Pero hay una diferencia importante entre "la instrumentación existe y funciona" y "la
instrumentación fue probada bajo las condiciones para las que existe". Este proyecto académico
nunca enfrentó un incidente real de producción, ni un volumen de tráfico que estresara realmente el
sistema de alertas. El valor real de Application Insights, por ejemplo, aparece cuando hay que
diagnosticar por qué el percentil 95 de latencia subió la semana pasada con tráfico real — algo que
este proyecto no ha tenido oportunidad de ejercitar. Por eso separé explícitamente, en cada fila
de la tabla, "qué validé" de "qué propósito cumple en producción": son afirmaciones distintas y
quiero que quedé claro cuál estoy haciendo en cada caso.

---

## Diapositiva 9 — Arquitectura del Conocimiento

Esta diapositiva existe porque quiero anticipar la pregunta obvia: si Azure AI Search aparece en la
arquitectura, ¿por qué no está haciendo búsqueda real hoy? La respuesta arquitectónica es
deliberada, no un descuido.

RAG —Retrieval-Augmented Generation— es el patrón que hace que una respuesta del asistente esté
fundamentada en un documento real y citable, en lugar de depender únicamente de lo que el modelo
aprendió durante su entrenamiento. Eso importa muchísimo en un dominio regulado como seguros, donde
una respuesta incorrecta sobre cobertura tiene consecuencias reales. Elegí Azure AI Search como
motor de recuperación por su integración nativa con el resto de la plataforma y porque soporta
búsqueda híbrida —combinando texto y búsqueda vectorial por significado—, no solo coincidencia de
palabras clave.

Ahora, el estado actual: el servicio está provisionado en Azure, pero su índice todavía no está
poblado —no existe aún un pipeline de ingestión de documentos reales ejecutado. Por eso el
proveedor de conocimiento activo hoy es una versión local, con documentos sintéticos versionados
directamente en el repositorio. No es una limitación de la arquitectura, es una limitación de
alcance del proyecto académico: no había pólizas, manuales de suscripción ni procedimientos reales
que indexar. En un escenario de producción, ese mismo componente —sin cambios de código, solo
cambiando la configuración del proveedor— indexaría pólizas reales, manuales de suscripción,
procedimientos de siniestros y documentación corporativa vigente. La interfaz ya existe; lo que
falta es el contenido real y su gobierno de acceso.

---

## Diapositiva 10 — DevOps

El pipeline de CI/CD tiene seis etapas encadenadas: calidad de código, puertas de calidad y
seguridad, construcción de la imagen Docker, validación de infraestructura como código con Bicep,
despliegue al entorno DEV, y finalmente smoke tests automáticos contra el sistema real ya
desplegado. El principio de diseño aquí es simple: ninguna etapa avanza si la anterior falla —no
hay manera de que un cambio con pruebas rotas o una vulnerabilidad de seguridad conocida llegue a
desplegarse.

Ahora quiero hablar directamente del punto que un evaluador de arquitectura seguramente va a
cuestionar: ¿por qué Azure Functions, que aparece marcado como parte de la arquitectura, no está
desplegado? La respuesta honesta es una restricción externa de la suscripción: la suscripción de
Azure usada para este proyecto tiene cuota cero para el espacio de nombres Microsoft.Web, que es
donde vive Azure Functions. No fue un solo intento fallido — fueron múltiples intentos reales de
despliegue, probando distintos SKU de plan de hosting, y los cuatro fallaron exactamente por la
misma razón de cuota. Esto está documentado en el ADR correspondiente con la evidencia completa de
cada intento.

Lo que quiero que quede claro es la distinción entre una limitación de arquitectura y una
limitación de entorno: el código de Azure Functions existe, está probado, y la infraestructura como
código para desplegarlo también existe y fue validada — lo único que falta es la cuota de la
suscripción para materializarlo. Por eso el sistema hoy corre con el mismo conjunto de
herramientas determinista, pero en un runtime distinto: dentro del propio proceso de la API en
lugar de en un endpoint serverless separado. La abstracción que permitió esto — que ya mencioné en
la diapositiva de principios — es lo que hace que cambiar de runtime, el día que haya cuota
disponible, sea un cambio de configuración y no una reescritura de código.

---

## Diapositiva 11 — Resultados

Esta diapositiva resume la evidencia de madurez del proyecto, y quiero presentarla con el mismo
espíritu de honestidad que el resto de la defensa: no es un listado de logros sin contexto, es una
medición con su propia metodología explícita.

El hallazgo más importante de todo el proceso de revisión de arquitectura fue la ausencia de
autenticación —era, con evidencia, el único bloqueador que impediría considerar este sistema para
un piloto con usuarios reales. Una vez implementada Microsoft Entra ID de extremo a extremo, ese
hallazgo y su consecuencia directa —el IDOR en el historial de conversaciones— quedaron resueltos,
y no solo diseñados: hay pruebas de regresión dedicadas que simulan dos identidades distintas e
intentan, deliberadamente, que una lea la conversación de la otra. La prueba falla en conseguirlo,
que es exactamente el resultado esperado.

Sobre el puntaje de madurez: notén que bajó de 3.8 a 3.5 entre dos evaluaciones consecutivas, y
quiero explicar por qué eso no es un retroceso. La segunda evaluación aplicó una metodología más
estricta, separando cinco dimensiones —escalabilidad, DevOps, arquitectura de IA, orquestación
multiagente y madurez empresarial— que la primera evaluación había agrupado en categorías más
amplias. La dimensión de seguridad en sí se mantuvo idéntica en ambas evaluaciones. Es un ejemplo
concreto de cómo una medición más rigurosa puede producir un número menor sin que el sistema
subyacente haya empeorado — y prefiero mostrar esa honestidad metodológica a maquillar el número.

---

## Diapositiva 12 — Evolución Futura

Esta diapositiva no es una lista de deseos genérica — cada punto corresponde a un hallazgo
específico, identificado y documentado durante el propio proceso de revisión de arquitectura del
proyecto, no algo que se me ocurrió al final.

Los primeros tres puntos son continuaciones directas de decisiones que ya expliqué: habilitar Azure
Functions en cuanto exista cuota, conectar con sistemas reales en lugar de datos sintéticos, y
poblar el índice de Azure AI Search con contenido real. Ninguno de los tres requiere rediseñar la
arquitectura — son activaciones de capacidades que ya existen en el diseño.

Quiero detenerme en el punto de aprobación humana por confianza, porque es el hallazgo más
interesante desde el punto de vista arquitectónico: el diseño original de este sistema nombraba
explícitamente un mecanismo de escalamiento humano cuando la confianza en la intención detectada
fuera baja —apropiado para un dominio como seguros, donde una decisión ambigua no debería
resolverse solo automáticamente. Al revisar el código en profundidad durante la evaluación final de
arquitectura, encontré que ese mecanismo nunca se implementó: la confianza es hoy un valor binario,
uno o cero, sin un umbral real ni una ruta de escalamiento. Es una brecha real entre lo documentado
y lo construido, y prefiero mostrarla explícitamente en esta diapositiva que dejarla oculta.

Los últimos puntos —Private Endpoints, autoescalado real y endurecimiento de producción— son
decisiones ya tomadas y documentadas de diferir ciertas capacidades en el entorno de desarrollo por
una razón explícita de costo, no un olvido. Cada una tiene su propio registro de decisión
arquitectónica indicando exactamente qué se necesitaría para activarla.

---

## Diapositiva 13 — Conclusiones

Para cerrar, quiero volver a la pregunta con la que empecé esta defensa: no solo qué se construyó,
sino por qué se construyó así.

Lo que se logró es concreto y verificable: una arquitectura multiagente que funciona, con
autenticación empresarial completa y su hallazgo más crítico —el aislamiento de datos entre
usuarios— resuelto y comprobado con pruebas, no solo diseñado. Pero lo que quiero que quede como
idea central de esta defensa es que cada decisión de arquitectura que presenté —el modelo de
lenguaje, el cómputo, la base de datos, la identidad— respondió a una restricción real del
problema: latencia y costo para el modelo, complejidad operativa proporcional para el cómputo, la
forma natural del dato para la base de datos. Ninguna fue una preferencia tecnológica sin
justificación.

El acoplamiento débil mediante interfaces —el principio que mencioné al inicio— es lo que hizo
posible incorporar autenticación empresarial completa, y diseñar la capa serverless, sin reescribir
la lógica de negocio existente en ningún momento. Y las limitaciones que mostré sin ocultar —la
cuota de Azure Functions, el escalamiento humano no implementado, el índice de búsqueda vacío— no
son fallas de la arquitectura: son exactamente el tipo de brecha entre diseño e implementación que
un proceso de revisión de arquitectura serio debe encontrar y documentar, en lugar de dejar oculta
hasta que aparezca en producción.

Con eso, quedo abierto a preguntas.

---
