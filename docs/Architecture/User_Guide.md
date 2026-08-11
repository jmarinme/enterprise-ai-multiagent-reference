# TMX Enterprise AI Reference Platform

## User Guide

---

### Cover Information

| | |
|---|---|
| **Document Title** | TMX Enterprise AI Reference Platform — User Guide |
| **Version** | 1.1 (PBI-10-06: refreshed after Microsoft Entra ID integration) |
| **Date** | 2026-08-11 |
| **Project Name** | TMX Enterprise AI Reference Platform (academic reference implementation) |
| **Intended Audience** | Business users: Claims Representatives, Brokers, Commercial Staff, and other internal users interacting with the conversational assistant |

> **Note:** This is an academic reference project. Every policy, claim, broker, customer, and commission mentioned in this guide is **synthetic** — no real customer or business data exists anywhere in this platform.

---

## 1. Purpose

The TMX Enterprise AI Reference Platform is a conversational assistant that helps business users
handle common insurance-related requests through a natural, chat-based interface instead of
navigating multiple forms or systems. A user simply types what they need in plain language —
Spanish or English — and the assistant identifies the right specialist area, asks for exactly the
information still needed, and completes the request.

**Business value:**

- A single conversational entry point for three different business areas (claims, broker
  services, commercial intake) — the user does not need to know which system or department
  handles their request.
- The assistant remembers relevant facts already provided (such as a validated policy number)
  even if the conversation moves to a different topic, so the user is not asked to repeat
  themselves unnecessarily (see Scenario 5).
- Every response is generated from the platform's own approved information sources — the
  assistant does not guess or fabricate policy status, payment status, coverage, or commission
  data; it looks these up through the same underlying checks a human representative would use.
- Every conversation is saved automatically, so a user can leave and return to a prior
  conversation later.

---

## 2. Intended Users

| User type | How they use the platform |
|---|---|
| **Claims Representatives** | Guide a caller through reporting a claim, or use the assistant themselves to walk through what information a claim notice requires. |
| **Brokers** | Check policy or transaction status, and review or request payment of their own commissions. |
| **Commercial Staff** | Register a new commercial insurance inquiry (a prospective business customer) for internal follow-up. |
| **Internal Business Users** | Anyone at the organization who needs a quick answer about a synthetic policy, claim, or commission without navigating a separate back-office system. |

This platform is an internal, demonstration-oriented tool. It is not a public-facing customer
self-service application.

---

## 3. Accessing the Application

The platform is accessed through a standard web browser, at the address provided by your
project/IT contact. No installation is required.

### 3.1 Sign in with Microsoft

The application requires signing in with a Microsoft account before it can be used. Opening the
application shows a sign-in screen — not the chat interface — until sign-in completes.

1. Select **"Iniciar sesión con Microsoft"** ("Sign in with Microsoft").
2. A Microsoft sign-in window (a popup) opens.

*Figure 1a – Insert screenshot of the sign-in screen ("Iniciar sesión con Microsoft" button).*

### 3.2 Selecting an account

In the Microsoft sign-in popup, choose the Microsoft account to use (or enter your work,
school, or personal Microsoft account credentials if none is already remembered by the browser).
This screen is presented directly by Microsoft — the application itself never asks for or sees a
password. Once the popup completes, it closes automatically and the chat interface loads.

*Figure 1b – Insert screenshot of the Microsoft account-selection popup.*

### 3.3 Authenticated session

Once signed in, the header at the top of the application shows your account's display name and a
connectivity status indicator. Every conversation created from this point on is associated with
your signed-in identity — not with the browser you happen to be using (Section 3.5).

*Figure 1c – Insert screenshot of the signed-in header showing the account name and "Cerrar sesión" button.*

### 3.4 Session expiration

Your sign-in is kept active automatically in the background — most of the time, you will never
notice a token being renewed. If your session has been inactive long enough that it can no
longer be renewed automatically, the application will prompt you to sign in again (a new
Microsoft sign-in popup) the next time it needs to send a request. Simply complete the sign-in
again as in Section 3.1–3.2; your prior conversations are not lost — they reappear in the
sidebar's conversation history once you are signed in again (Section 3.5).

### 3.5 Conversation history after login

Conversation history is tied to your **signed-in identity**, not to the browser or device — a
change from earlier versions of this platform. Signing in with the same Microsoft account from a
different browser or computer shows the same conversation history; signing in with a
**different** Microsoft account shows only that account's own conversations, never another
user's. This is enforced by the platform itself, not merely by the interface — see the
platform's Administrator documentation for the technical detail.

### 3.6 Sign out

Select **"Cerrar sesión"** ("Sign out") in the header to end your session. You are returned to
the sign-in screen (Section 3.1). Signing out does not delete any conversation — signing back in
with the same account shows the same conversation history as before.

---

## 4. User Interface Overview

The application is a single-page chat interface with three areas, all visible at once. No
separate screens or menus exist beyond what is described below — this section documents only
what is actually implemented.

### 4.1 Sidebar (left panel)

- **"+ Nueva conversación" ("+ New conversation") button** — starts a brand-new conversation. The
  previous conversation is not deleted; it remains available in the conversation history below.
- **Search box** — filters the conversation history list by title as you type.
- **Conversation history list** — every previous conversation for this browser, with its title and
  the date/time it was last updated, most recent first. Selecting one reloads that entire
  conversation into the chat area.
- **Example prompts** — a short list of ready-to-use starter messages ("Siniestros", "Servicios a
  corredores", "Nuevos negocios", "Siniestros + Conocimiento"), each pre-written to route to the
  correct specialist area. Selecting one sends it immediately.
- A reminder note that only synthetic data is used — no real policies, claims, or customers.

*Figure 2 – Insert screenshot of the Sidebar showing conversation history and example prompts.*

### 4.2 Chat window (center panel)

- **Response area** — the running conversation, with the user's own messages and the assistant's
  replies shown in sequence.
- **Specialist badge** — each assistant reply that comes from a specific specialist area is
  labeled with a friendly name: "Siniestros" (Claims), "Servicios a Corredores" (Broker
  Services), "Nuevos Negocios" (Commercial Intake), or "Asistente" (general assistant, used when
  the request does not match a specific area). The user is never shown an internal technical name.
- **Source references** — when a reply is based on the platform's reference documents (for
  example, answering "what documents do I need to report a claim?"), the reply is marked "Basado
  en N fuente(s)" ("Based on N source(s)") with a short numbered reference list underneath, so the
  user can see the reply is grounded in an actual document rather than invented.
- **Typing indicator** — a brief "Analizando…" ("Analyzing…") indicator appears while the
  assistant is preparing a reply.
- **Error messages** — if a message cannot be sent (for example, a connectivity problem), the
  assistant shows a generic notice ("Lo sentimos, ocurrió un problema al conectar con el
  Asistente de TMX. Por favor intenta de nuevo.") together with a "Reintentar" ("Retry") button
  that resends the same message. No technical error detail is ever shown to the user.
- **Message input box** — where the user types their message.

*Figure 3 – Insert screenshot of the main chat window with an example conversation.*

### 4.3 What does NOT exist

To avoid any confusion when comparing this guide to the application: there is no dashboard, no
settings screen, no file-upload control, no admin panel, and no separate screen per specialist
area — every interaction happens in the single chat window described above.

---

## 5. Business Scenario 1 — Checking the Status of a Policy

This scenario uses the platform's Broker Services capability to check whether a policy is
currently active and whether payments are up to date, using synthetic policy `SYN-POL-0002`.

**Conversation:**

| Turn | Speaker | Message |
|---|---|---|
| 1 | User | Hola, quiero consultar información con mi corredor. |
| 1 | Assistant (Servicios a Corredores) | ¿En qué te puedo ayudar — consultar el estado de una póliza o transacción, o revisar tus comisiones? |
| 2 | User | El estado de mi póliza. |
| 2 | Assistant | Por favor indica el número de póliza sintética. |
| 3 | User | SYN-POL-0002 |
| 3 | Assistant | Estado de la póliza SYN-POL-0002: active. Esta póliza tiene un pago pendiente. |

*Figure 4 – Insert screenshot of this Broker Services policy-status conversation.*

**What the user should expect:**

- The assistant first asks what kind of help is needed (policy/transaction status, or
  commissions) unless the opening message already makes this clear.
- Only one additional piece of information is needed for a policy-status check: the policy
  number.
- The response always states the policy's status as a plain fact (`active`, `lapsed`, or
  `cancelled`) together with whether payments are current — the assistant reports this
  information, it does not interpret or act on it (for example, it will never cancel a policy or
  change its status).

---

## 6. Business Scenario 2 — Reporting a Claim

This scenario demonstrates a complete claim notification using synthetic policy `SYN-POL-0001`
(an active auto policy with payments current).

**Conversation:**

| Turn | Speaker | Message |
|---|---|---|
| 1 | User | Necesito reportar un siniestro. |
| 1 | Assistant (Siniestros) | Claro. ¿A nombre de quién está la póliza? |
| 2 | User | SYN-POL-0001 |
| 2 | Assistant | Cuéntame sobre el incidente: ¿qué día ocurrió (AAAA-MM-DD), dónde fue, y qué tipo de siniestro es (colisión, robo, incendio, daño por agua, clima, vandalismo, otro)? |
| 3 | User | 2026-08-01 |
| 3 | Assistant | Hasta ahora tengo: ✔ póliza ✔ fecha. Solo me falta: ¿Dónde ocurrió el incidente? ¿Qué tipo de siniestro fue…? |
| 4 | User | en mi casa |
| 4 | Assistant | Hasta ahora tengo: ✔ póliza ✔ fecha ✔ ubicación. Solo me falta: ¿Qué tipo de siniestro fue…? |
| 5 | User | fue una colisión |
| 5 | Assistant | Hasta ahora tengo: ✔ póliza ✔ fecha ✔ ubicación ✔ tipo de siniestro. Solo me falta: ¿Podrías describir brevemente qué sucedió? |
| 6 | User | Otro carro me golpeó estando estacionado. |
| 6 | Assistant | Solo me falta: ¿Cuál es el mejor teléfono para contactarte? |
| 7 | User | 555-123-4567 |
| 7 | Assistant | Solo me falta: ¿Hubo personas lesionadas, y estuvieron involucrados terceros? (sí/no para cada una) |
| 8 | User | No hubo personas lesionadas ni terceros involucrados. |
| 8 | Assistant | Solo me falta: ¿El vehículo todavía puede circular? |
| 9 | User | Sí, el vehículo puede circular. |
| 9 | Assistant | Tu póliza está vigente. Los pagos de esta póliza están al corriente. Tu cobertura es "Cobertura amplia", con suma asegurada de $250,000.00 y deducible de $5,000.00. Antes de registrar tu siniestro, confirmemos los datos: póliza SYN-POL-0001, incidente del 2026-08-01 en "en mi casa", tipo "colisión". El vehículo puede circular. ¿Confirmas que deseamos registrar tu siniestro con esta información? (sí/no) |
| 10 | User | Sí |
| 10 | Assistant | Tu aviso de siniestro ha sido registrado. Tu número de referencia es SYN-CLM-2026-0001. Synthetic Adjuster Rivera fue asignado a tu siniestro SYN-CLM-2026-0001 y te contactará pronto. |

*Figure 5 – Insert screenshot of the Claims conversation (recommend capturing turns 1–2 and the confirmation/registration turns 9–10).*

**What the user should expect:**

1. **Policy validation** — the assistant asks for the policy number and, once every other detail
   has been collected, checks it and reports the policy's status, payment status, and coverage as
   plain facts.
2. **Incident information** — the assistant asks for the event date, location, and type of loss in
   a single combined question, then narrows to whatever is still missing on each following turn —
   the user never needs to repeat information already given.
3. **Follow-up questions** — contact phone number, whether anyone was injured, whether any other
   party was involved, and (for an auto claim) whether the vehicle can still be driven.
4. **Confirmation** — before anything is registered, the assistant summarizes everything collected
   and asks for an explicit yes/no confirmation. Answering "no" does not discard the information —
   it asks what the user would like to correct and lets them re-supply just that detail.
5. **Claim reference number** — once confirmed, the assistant registers the claim and returns a
   reference number in the format `SYN-CLM-<year>-<sequence>` (the exact sequence number depends
   on how many claims have already been registered in the current session) and the name of the
   synthetic adjuster assigned to follow up.

> **Note:** The assistant only records the facts reported — per the platform's design, it never
> approves, rejects, or determines coverage for a claim. A final coverage decision is always made
> by a human.

---

## 7. Business Scenario 3 — Checking Broker Services

This scenario demonstrates a commission inquiry and payment request using synthetic broker
`Synthetic Brokerage One` (broker ID `SYN-BRK-0001`).

**Conversation:**

| Turn | Speaker | Message |
|---|---|---|
| 1 | User | Hola, quiero conocer mis comisiones. |
| 1 | Assistant (Servicios a Corredores) | ¿Con qué broker trabajas, y qué período te gustaría revisar? |
| 2 | User | Soy Synthetic Brokerage One, período 2026-Q1. |
| 2 | Assistant | Comisión de 2026-Q1: $1,250.00 (estado: available). ¿Te gustaría solicitar el pago de esta comisión? (sí/no) |
| 3 | User | Sí, por favor. |
| 3 | Assistant | Tu solicitud de pago de comisión ha sido registrada. Referencia: SYN-PAYREQ-2026-0001. |

*Figure 6 – Insert screenshot of the Broker Services commission-inquiry-and-payment-request conversation.*

**What the user should expect:**

- **Commission inquiry** — the assistant asks for the broker's name (a typed broker ID also
  works, and skips the name-lookup step entirely) and the period to review, together in one
  question.
- **Broker identification** — a broker name is automatically matched to the correct account; the
  user never needs to know or type an internal broker ID.
- **Policy inquiry** — the same Broker Services area also handles "what is the status of policy
  X" (Scenario 1) and "what is the status of transaction X" — the assistant asks which kind of
  help is needed if it is not already clear from the first message.
- **Commission amount and status** — reported as a plain fact (`available`, `pending`, or `paid`).
  Only a commission already marked `available` can be requested for payment; the assistant will
  not offer the payment-request question otherwise.
- If a payment request is confirmed, a payment-request reference number is returned in the format
  `SYN-PAYREQ-<year>-<sequence>`.

---

## 8. Business Scenario 4 — Registering a New Business Opportunity

This scenario demonstrates the Commercial Intake workflow — collecting the information needed to
register a new commercial insurance lead for internal follow-up.

**Conversation:**

| Turn | Speaker | Message |
|---|---|---|
| 1 | User | Necesito una cotización para asegurar mi empresa. |
| 1 | Assistant (Nuevos Negocios) | ¿Cuál es el nombre de tu empresa o negocio? |
| 2 | User | Constructora Sintética del Norte |
| 2 | Assistant | ¿Cuál es el nombre completo de la persona de contacto? |
| 3 | User | María Fernanda López |
| 3 | Assistant | ¿Prefieres que te contactemos por correo electrónico o por teléfono? |
| 4 | User | Por correo electrónico. |
| 4 | Assistant | ¿Cuál es el mejor correo electrónico para contactarte? |
| 5 | User | maria.lopez@example.com |
| 5 | Assistant | ¿Qué tipo de seguro o cobertura estás buscando? |
| 6 | User | Seguro de responsabilidad civil para construcción. |
| 6 | Assistant | ¿Podrías describir brevemente tu negocio o el riesgo que te gustaría cubrir? |
| 7 | User | Somos una constructora mediana, con unos 40 empleados, y manejamos proyectos residenciales. |
| 7 | Assistant | Gracias — tu solicitud ha sido registrada. Tu número de referencia es SYN-LEAD-2026-0001. Un representante te contactará por correo electrónico. |

*Figure 7 – Insert screenshot of the Commercial Intake conversation.*

**Step-by-step explanation:**

1. **Company identification** — name of the business.
2. **Contact person** — full name of the person to follow up with.
3. **Preferred contact channel** — email or phone; the assistant then asks only for the matching
   detail (an email address, or a phone number).
4. **Insurance need** — the type of coverage being sought.
5. **Risk description** — a short description of the business or the risk to be covered.
6. **Registration** — once every field is collected, the assistant registers the lead and returns
   a tracking reference in the format `SYN-LEAD-<year>-<sequence>`, plus a confirmation of which
   channel will be used for follow-up.

> **Important:** Per the platform's design, this step **never** produces a quote, a premium, or a
> guarantee of coverage acceptance — despite the user's opening message asking for a "cotización"
> (quote). The assistant's role here is limited to collecting information and registering the
> inquiry for a human underwriter/commercial team to follow up on.

---

## 9. Business Scenario 5 — Conversation Memory

This scenario shows how the assistant keeps track of relevant facts as the conversation moves
between specialist areas, so the user is not asked to repeat information already given.

**Setup:** the user begins exactly as in Scenario 2 — reporting a claim for policy `SYN-POL-0001`
— and provides the policy number on the second turn ("SYN-POL-0001"). At this point the platform
has already recorded, internally, that this conversation involves policy `SYN-POL-0001`.

**Claims → Broker Services:**

| Turn | Speaker | Message |
|---|---|---|
| 3 | User | Ahora quiero consultar el estado de esa póliza con mi corredor. |
| 3 | Assistant (Servicios a Corredores) | Estado de la póliza SYN-POL-0001: active. Los pagos de esta póliza están al corriente. |

Notice that the assistant switched to Broker Services and answered immediately — it **did not
ask for the policy number again**, because it was already established earlier in the same
conversation while reporting the claim.

**Broker Services → Commercial Intake:**

Continuing the same conversation, the user then asks about a new business opportunity:

| Turn | Speaker | Message |
|---|---|---|
| 4 | User | También quisiera una cotización para asegurar otro negocio que tengo. |
| 4 | Assistant (Nuevos Negocios) | ¿Cuál es el nombre de tu empresa o negocio? |
| 5 | User | Constructora Sintética del Norte |
| 5 | Assistant | ¿Prefieres que te contactemos por correo electrónico o por teléfono? |

Notice that the assistant asked for the **company name**, but skipped directly to asking for the
**preferred contact channel** — it did not ask "what is the contact person's name?" a second time,
because that fact (the caller's own name, established earlier while validating the claim's
policy) was already known.

*Figure 8 – Insert screenshot showing a conversation that moves from Siniestros to Servicios a Corredores to Nuevos Negocios, ideally with the specialist badges visible on each reply.*

**What the user experiences:** switching topics feels like talking to one assistant that
remembers the conversation, not three separate systems. Only facts the platform actually tracks
(currently: customer/contact name, broker identity, policy number, claim number, business name,
incident date/type/location, and coverage) carry over automatically — a detail outside that list
(for example, a phone number given to one specialist) may still be asked again by a different
one.

---

## 10. Frequently Asked Questions (FAQ)

**Why am I being asked for additional information?**
Each specialist area needs a specific, fixed set of details to complete a request (for example, a
claim needs the incident date, location, and type of loss). The assistant asks for exactly what
is still missing, one step at a time, rather than requiring a long form up front.

**Why do I need my policy number?**
The policy number is how the assistant looks up your actual policy status, payment status, and
coverage from the platform's records — without it, none of that information can be confirmed.

**Can I switch topics during the conversation?**
Yes. You can move between claims, broker services, and commercial inquiries freely within the
same conversation, and the assistant will route each message to the right specialist area
automatically. Facts already established earlier are reused where possible (see Scenario 5).

**What happens if I provide incorrect information?**
If a policy, transaction, or broker ID cannot be found, the assistant tells you directly (for
example: "No encontramos una póliza con el número '...'. ¿Puedes verificarlo y proporcionarlo de
nuevo?") and asks you to double-check and provide it again. Nothing else you had already provided
is lost or needs to be re-entered.

**How do I restart the conversation?**
Select "+ Nueva conversación" in the sidebar. This starts a fresh conversation; your previous
conversation is not deleted and remains available in the conversation history list.

**Can I upload a document (like a photo of damage or a police report)?**
Not in this version of the platform — there is no file or document upload control anywhere in the
interface.

**Does the assistant make the final decision on my claim or quote?**
No. The assistant only collects information and records it — it never approves or rejects a
claim, determines coverage, or issues a quote or premium. Those decisions are made by a human.

---

## 11. Best Practices

- **Provide complete information when possible** — a message that answers more than one question
  at once (for example, naming your broker and the commission period together) is understood
  correctly and speeds up the conversation.
- **Answer follow-up questions directly** — the assistant asks one thing at a time when
  information is missing; a direct answer keeps the conversation moving smoothly.
- **Use the correct policy, broker, or transaction number** when you have it — this lets the
  assistant confirm real details immediately instead of asking you to verify and retry.
- **Review the confirmation before submitting** — for a claim, the assistant always summarizes
  everything collected and asks for explicit confirmation before registering anything; take a
  moment to check it is correct, and say "no" if something needs to change.
- **Stay in one conversation when topics are related** — switching between claims, broker
  services, and commercial questions within the same conversation lets the assistant reuse facts
  it already knows (Scenario 5); starting a brand-new conversation for an unrelated topic means
  starting fresh.

---

## 12. Known Limitations

Only limitations that are actually present in this version of the platform are listed here.

- **A Microsoft account is required.** There is no anonymous or guest access — every use of the
  application requires signing in with Microsoft (Section 3).
- **Synthetic data only.** Every policy, claim, broker, customer, and commission referenced by the
  assistant is fabricated for demonstration purposes — there is no connection to any real
  business system or real customer data.
- **No document/file upload.** The interface has no capability to attach a photo, PDF, or any
  other file to a conversation.
- **No quote, premium, or coverage decision is ever produced.** The Commercial Intake area only
  registers an inquiry for human follow-up; the Claims area only records facts, never a coverage
  determination.
- **Memory carries over only specific facts.** As described in Scenario 5, only a fixed set of
  facts (customer/contact name, broker identity, policy number, claim number, business name,
  incident date/type/location, and coverage) is automatically reused across topics in the same
  conversation — any other detail may be asked again by a different specialist area.
- **A conversation cannot be deleted or renamed** from the interface — only started fresh ("+
  Nueva conversación") or reopened from the history list.
- **The interface is presented in Spanish by default** (welcome message, example prompts, and
  sidebar labels). The assistant does understand and can respond in English as well, but the
  visible interface elements themselves are Spanish-first.

---

## 13. Troubleshooting

| Problem | Possible Cause | Recommended Action |
|---|---|---|
| The assistant replied with a general/unrelated answer instead of connecting me to the right area | The message did not contain a word the assistant recognizes for a specific area (claims, broker services, or commercial) | Rephrase using a more direct term for what you need, e.g., "reportar un siniestro," "mis comisiones," or "cotización para mi empresa" |
| I got a message saying there was a problem connecting, with a "Reintentar" (Retry) button | A temporary connectivity issue occurred while sending the message | Select "Reintentar" to resend the same message; if the problem continues, try again shortly |
| The assistant asked me for my policy/broker/transaction number again after I already gave it | The number provided was not found in the platform's synthetic records, so the assistant is asking you to verify and re-enter it | Double-check the number and provide it again exactly as issued (e.g., `SYN-POL-0001`) |
| I switched topics and the assistant asked me something I already answered earlier | That specific detail is not one of the facts the platform automatically carries across topics (Section 12) | Provide the detail again for the new specialist area — this is expected behavior, not an error |
| I don't see my previous conversation in the sidebar | You may be signed in with a different Microsoft account than the one used to create that conversation | Conversation history is tied to your signed-in Microsoft account, not the browser (Section 3.5) — confirm you are signed in with the same account, using "Cerrar sesión" and signing in again if needed |
| The sign-in popup did not appear, or closed without completing sign-in | The browser may have blocked the popup, or the sign-in was cancelled | Allow popups for this site and try "Iniciar sesión con Microsoft" again |
| I was suddenly asked to sign in again in the middle of using the application | Your session had been inactive long enough that it could no longer be renewed automatically (Section 3.4) | Sign in again; your previous conversations are not lost and reappear once signed in |
| The claim/lead reference number I received looks different from a prior example in this guide | Reference numbers include a sequence number that increases with each new record registered | This is expected — the exact number will vary; the format itself (e.g., `SYN-CLM-2026-000x`) is what matters |

---

## 14. Quick Reference Guide

*(This page is formatted for standalone printing.)*

### TMX Enterprise AI Reference Platform — Quick Reference

**What it does:** A chat-based assistant for synthetic Claims, Broker Services, and Commercial
Intake requests — no forms, no separate systems.

**Main capabilities**

| Area | What you can ask for |
|---|---|
| Siniestros (Claims) | Report a claim; check policy/payment/coverage as part of that flow |
| Servicios a Corredores (Broker Services) | Check a policy or transaction status; review or request payment of commissions |
| Nuevos Negocios (Commercial Intake) | Register a new commercial insurance inquiry for follow-up |

**Common user actions**

- Sign in with "Iniciar sesión con Microsoft" the first time you open the application.
- Type your request in plain Spanish or English — no special commands needed.
- Answer the assistant's follow-up questions one at a time.
- Select "+ Nueva conversación" to start over.
- Select any item in the conversation history to reopen it.
- Select "Reintentar" if a message fails to send.
- Select "Cerrar sesión" to sign out.

**Typical conversation flow**

1. Describe what you need in your own words.
2. The assistant identifies the right specialist area and asks for any missing details, one at a
   time.
3. For a claim: review the summary and confirm (yes/no) before it is registered.
4. Receive a reference number (claim, payment request, or lead) where applicable.

**Helpful tips**

- Have your policy number, broker name/ID, or transaction reference ready when relevant.
- You can switch between topics in the same conversation — relevant facts are remembered.
- No real data — this platform uses synthetic policies, claims, and customers only.

---

## Cross-references

This guide intentionally does not repeat deployment or administration content. For those topics,
see:

- `Deployment_Guide.md` — infrastructure and release process (technical/IT audience).
- `Administrator_Guide.md` — day-to-day operation, monitoring, and troubleshooting (technical/IT
  audience).
