# Loan Default Risk App: Requirements & User Stories

## User Roles
- Loan Officer
- Supervisor
- Admin/System Operator

## User Stories & Features

### 1. Automated Early Stage Reminders
- As a loan officer, I want the system to automatically send reminders (SMS/WhatsApp/call scripts) to clients based on delinquency buckets and behavior, so I can focus on higher-risk cases.
- As an admin, I want to configure reminder templates and schedules.

### 2. Risk Scoring & Visit List Prioritization
- As a loan officer, I want my daily visit list to be prioritized by client risk (e.g., >15 days overdue, repeated late payments), so I can optimize my field visits.
- As a supervisor, I want to view and adjust visit plans for my team.

### 3. Real-Time Visit Plans & Scripts
- As a loan officer, I want to receive a daily visit plan with suggested negotiation options (rescheduling, partial payment) aligned with policy.
- As a supervisor, I want to review and approve visit plans if needed.

### 4. Field Feedback & Adaptive Planning
- As a loan officer, I want to submit field feedback (client hardship, repayment promise, dispute) via the app.
- As a supervisor, I want to be notified of escalations and review flagged cases.
- As a system, I want to adapt the next day’s plan based on feedback.

### 5. KPI Tracking & Coaching
- As a supervisor, I want to track collection KPIs per officer (percent current, avg days overdue, reschedule rate).
- As a supervisor, I want the system to suggest coaching tips or training modules when performance dips.

### 6. Security & Compliance
- As an admin, I want secure authentication, authorization, and audit logging.
- As a system, I want to ensure data privacy and compliance with regulations.

## Technical Tasks (Initial)
- Design system architecture and select tech stack
- Set up project structure and version control
- Implement data ingestion and processing pipeline
- Develop risk scoring model
- Build backend API for visit plans, feedback, and reporting
- Integrate SMS/WhatsApp/call APIs
- Develop frontend/dashboard (web or mobile)
- Implement authentication and authorization
- Set up CI/CD, monitoring, and logging
- Write documentation and user guides

---
This document will be updated as requirements evolve and features are refined.