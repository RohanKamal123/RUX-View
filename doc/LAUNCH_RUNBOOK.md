# Vision OS Launch Day Operations Runbook

**Version**: 1.1  
**Last Updated**: 2026-06-18  
**Project**: Vision OS - AI-powered CCTV Intelligence SaaS for Bangladesh  
**Target**: First 100 users, 20 cameras per user  
**Stack**: Google Cloud Run + Docker + FastAPI + Firebase Auth  

> This runbook is the single source of truth for Vision OS launch day operations.  
> On-call team: 1-3 engineers  

---

## 1. Pre-Launch Checklist (24 Hours Before Launch)

> Complete all items at least 24 hours before public launch. Verify each checkbox.

- [ ] **Readiness Check**: Run `python scripts/health_check.py` and validate all green
- [ ] **Cloud Run Configuration**: Validate service has correct CPU (1), memory (512MB), max instances (10)
- [ ] **SSL/TLS Certificates**: Confirm custom domain SSL is provisioned and valid for 30+ days
- [ ] **Payment Gateway Test**: Process test transaction through bKash sandbox (amount: 10 BDT)
- [ ] **Firebase Auth Configuration**: Verify email/password providers enabled, SMS disabled for Bangladesh
- [ ] **Telegram Bot**: Test `/start`, `/help`, `/status` commands; verify webhook URL is correct
- [ ] **Backup Validation**: Confirm automated Neon PostgreSQL backups completed successfully in last 24h
- [ ] **Monitoring Setup**: Verify Cloud Monitoring dashboards, alert policies, and uptime checks active
- [ ] **Rollback Tag**: Create Git tag `pre-launch-v1.0` and push to origin
- [ ] **GDPR/DPDP Compliance**: Test data deletion API endpoint returns 200 with confirmation ID
- [ ] **Data Export**: Test GDPR data export endpoint produces valid JSON.zip archive
- [ ] **Cookie Consent Banner**: Verify appears on first load, blocks non-essential scripts until accepted
- [ ] **Status Page**: Confirm status page is configured and shows all systems operational
- [ ] **Team Notification**: Send launch reminder to on-call via Telegram group @visionos-ops
- [ ] **Load Test**: Run 50 concurrent user simulation using `locust` or artillery
- [ ] **Database Connection Pool**: Verify max connections set to 20, current usage < 50%
- [ ] **Log Retention**: Confirm Cloud Logging retention set to 30 days, export to BigQuery enabled
- [ ] **Emergency Contacts**: Verify all on-call engineers have received PagerDuty escalation policy
- [ ] **Cold Start Test**: Deploy dummy revision and measure cold start time < 1.5s
- [ ] **Rate Limiting**: Confirm API gateway rate limit set to 100 req/min per IP for auth endpoints

---

## 2. Launch Day Timeline

> Times are relative to public launch announcement (T=0). All times in BST (UTC+6).

| Time | Action | Owner | Verification |
|------|--------|-------|--------------|
| **T-60min** | Final readiness check, warm up Cloud Run instances | Primary Engineer | `curl -s https://api.visionos.app/health` returns 200 OK |
| **T-45min** | Enable internal testing mode (disable public signup temporarily) | Secondary Engineer | Firebase Auth shows 0 new signups in last 5min |
| **T-30min** | **Enable public signup** - Flip feature flag to allow registrations | Primary Engineer | Monitor Firebase Auth real-time dashboard |
| **T-15min** | Announce standby mode on social media/Telegram: "Launch in 15min!" | Secondary Engineer | Post to @visionosbd Telegram channel |
| **T-0** | **Official Launch Announcement** | Primary Engineer | Post launch announcement to: <br> - Twitter/X @visionosbd <br> - LinkedIn Company Page <br> - Telegram @visionosbd <br> - Facebook Page |
| **T+5min** | Verify first 5 signups completed successfully | Both Engineers | Check Firebase Auth > Users for new accounts with email_verified=true |
| **T+15min** | **End-to-End First User Journey Check**: <br> 1. Signup with test email <br> 2. Add camera (RTSP stream) <br> 3. Trigger AI detection <br> 4. Verify alert received | Primary Engineer | All steps complete < 2min, no errors in logs |
| **T+30min** | Review initial error rates and latency from Cloud Monitoring | Secondary Engineer | Error rate < 0.5%, p95 latency < 300ms |
| **T+1hr** | **Review Monitoring Dashboards** (see Section 3) | Both Engineers | All metrics within normal ranges |
| **T+2hr** | Check payment processing for any first purchases | Secondary Engineer | Verify 0 failed transactions in bKash dashboard |
| **T+4hr** | **Database Connection Pool Health**: <br> - Check active/idle connections <br> - Verify no connection leaks | Primary Engineer | Active connections < 10, idle < 5 |
| **T+6hr** | Mid-day metrics review: active users, camera count, AI usage | Secondary Engineer | Target: 10+ users, 50+ cameras connected |
| **T+8hr** | **Review First-Day Metrics** against success criteria | Both Engineers | See Section 3 for target metrics |
| **T+12hr** | Check for any abnormal log patterns or error spikes | Primary Engineer | No new error types in Error Reporting |
| **T+24hr** | **Post-Launch Retrospective Meeting** (30min) | All Engineers | Document lessons learned, update runbook |

---

## 3. Monitoring Dashboards

### Google Cloud Monitoring Dashboard
**Link**: https://console.cloud.google.com/monitoring/dashboards/dashboard/vision-os-production  
*(Replace with actual dashboard URL)*

### Key Metrics Table

| Metric | Target | Warning Threshold | Critical Threshold | Measurement Interval |
|--------|--------|-------------------|-------------------|----------------------|
| API p95 Latency | < 500ms | > 500ms | > 1000ms | 5 minutes |
| Error Rate (5xx) | < 1% | > 1% | > 5% | 5 minutes |
| Active Users (DAU) | > 50 | < 20 | < 10 | 1 hour |
| Camera Connections | > 200 | < 100 | < 50 | 15 minutes |
| AI API Cost (Daily) | < $50 | > $75 | > $100 | 1 hour |
| SLA Uptime (Monthly) | > 99.9% | < 99.9% | < 99.5% | 24 hours |
| Neon PG CPU Usage | < 60% | > 60% | > 80% | 5 minutes |
| Neon PG Storage | < 80% | > 80% | > 90% | 1 hour |
| Redis Memory Usage | < 70% | > 70% | > 85% | 5 minutes |
| Cloud Run Instance Count | < 8 | > 8 | > 12 | 5 minutes |

### Alert Thresholds Table

| Metric | Warning Level (Page Secondary) | Critical Level (Page Primary) | Notification Channels |
|--------|-------------------------------|-------------------------------|----------------------|
| API p95 Latency > 500ms for 10min | ✓ | - | Slack #alerts, Email |
| API p95 Latency > 1000ms for 5min | - | ✓ | PagerDuty, SMS, Telegram |
| Error Rate > 1% for 10min | ✓ | - | Slack #alerts, Email |
| Error Rate > 5% for 5min | - | ✓ | PagerDuty, SMS, Telegram |
| Active Users Drop > 80% from baseline | ✓ | - | Slack #alerts |
| Camera Connections Drop > 70% | ✓ | - | Slack #alerts |
| AI API Cost > $75/day projection | ✓ | - | Email Finance Lead |
| SLA Uptime < 99.9% (rolling 24h) | - | ✓ | PagerDuty, SMS, Telegram, Email Exec |
| Neon PG CPU > 80% for 10min | - | ✓ | PagerDuty, SMS |
| Neon PG Storage > 90% | ✓ | - | Slack #alerts, Email |
| Redis Memory > 85% for 10min | - | ✓ | PagerDuty, SMS |
| Cloud Run Instance Count > 12 for 10min | ✓ | - | Slack #alerts |

---

## 4. Redis Health Check

```bash
curl https://api.visionos.app/health | jq .redis
```

Expected:
```json
{"status": "ok", "latency_ms": "< 50"}
```

**If Redis is down**: BoT-SORT tracker falls back to stateless mode (Track IDs reset per request).
Gemini calls are NOT blocked by Redis failure. YOLO gate continues to work independently.

**Monitoring**: Set up a Cloud Monitoring alert on `/health` endpoint Redis response time > 200ms.

---

## 5. YOLO / ONNX Troubleshooting

### Symptom: "ONNX model not found" in logs
**Fix**: Ensure `yolov8n.onnx` is in the Docker image. Check Dockerfile COPY step includes `connect/models/`.

### Symptom: All frames reaching Gemini (YOLO not filtering)
**Fix**: Check Cloud Run logs for "YOLO gate" log lines. If absent, ONNX session failed to load — check `onnxruntime` version compatibility.

### Symptom: Pipeline consistently returns change_detected=False
**Fix**: Incident builder may be rate-limiting correctly. Check incident builder logs for "skip Gemini" reasons. If expected behaviour is wrong, check `GEMINI_INTERVAL_SEC` in `incident_builder.py` (default: 120s).

### Symptom: Missing track IDs after deploy
**Fix**: Redis transient — takes ~5s to repopulate. If tracks missing for >60s, check Upstash Redis dashboard for connection limits.

---

## 6. Incident Response Playbooks

### A. High Error Rate (>5%)
1. **Acknowledge** incident in PagerDuty, start incident timer
2. **Check** Cloud Logging for error spikes: `resource.type="cloud_run_revision" severity>=ERROR`
3. **Identify** failing endpoint from error logs (look for 5xx patterns)
4. **Rollback** to previous stable revision if deploy occurred < 30min ago
5. **Scale up** Cloud Run instances temporarily to handle load: `gcloud run services update vision-os --max-instances=20`
6. **Communicate** status update via status page and Telegram @visionos-ops

### B. Database Connection Issues
1. **Verify** Neon PostgreSQL instance status via Neon dashboard
2. **Check** connection count in logs: grep for `SQLAlchemy pool` 
3. **Restart** Neon instance via Neon console if connections stuck
4. **Clear** connection pool in application: Roll restart Cloud Run service
5. **Monitor** connection metrics for 15min after restart
6. **Postmortem**: Check for connection leaks in code, add pool timeout if needed

### C. Payment Processing Failure
1. **Check** bKash merchant dashboard for service alerts
2. **Verify** webhook endpoints are receiving callbacks: Check logs for `/webhook/bkash`
3. **Test** manual payment in sandbox mode to isolate issue
4. **Disable** bKash payment temporarily via feature flag if >5% failure rate
5. **Notify** finance team and affected users via email/template
6. **Restore** service once payment gateway confirms resolution

### D. AI Service Down
1. **Verify** Vertex AI API status: Check Google Cloud Status Dashboard
2. **Check** internal AI service health: `curl https://api.visionos.app/health`
3. **Enable** fallback mode: Serve cached results or basic motion detection
4. **Scale** if needed: Increase Cloud Run max instances
5. **Alert** users via in-app notification about temporary reduced accuracy
6. **Resume** full service once AI backend recovers

### E. Security Incident
1. **Isolate** affected systems: Revoke suspicious API keys/tokens
2. **Preserve** logs: Export relevant Cloud Logging entries to secure bucket
3. **Engage**: Contact DPO/Legal lead immediately (see Section 9)
4. **Investigate**: Use Cloud Security Scanner and audit login attempts
5. **Remediate**: Patch vulnerabilities, rotate compromised credentials
6. **Report**: Follow GDPR/DPDP breach notification timeline if data accessed

### F. Data Breach (GDPR/DPDP)
1. **Confirm** breach scope: What data was accessed/exfiltrated?
2. **Contain**: Revoke access, patch vulnerability within 2 hours
3. **Assess**: Determine if breach requires notification (risk to rights/freedoms)
4. **Notify**: DPO prepares notification for BD Data Protection Authority within 72 hours
5. **Inform**: Affected users via email/template within 72 hours if high risk
6. **Document**: All actions taken for regulatory review

### G. SLA Breach
1. **Verify** SLA calculation: Confirm downtime measurement accuracy
2. **Identify**: Root cause of downtime from incident logs
3. **Mitigate**: Implement fix to prevent recurrence
4. **Calculate**: Service credits owed per SLA terms (typically 10-25% of monthly fee)
5. **Communicate**: Notify affected customers with explanation and credit details
6. **Update**: Runbook and monitoring to prevent similar breaches

---

## 7. Rollback Procedure

> Execute when new deployment causes critical issues.

1. **Identify** problematic revision: `gcloud run services describe vision-os --format="value(spec.template.spec.containers[0].image)"`
2. **Get** list of revisions: `gcloud run revisions list --service vision-os --limit=5`
3. **Deploy** previous stable revision: `gcloud run services update vision-os --image=PREVIOUS_IMAGE_DIGEST`
4. **Wait** for rollout completion: `gcloud run services describe vision-os --format="value(status.conditions[?(@.type=='Ready')].status)"`
5. **Perform** health check: `curl https://api.visionos.app/health`
6. **Run** smoke tests: `pytest tests/smoke/ -v`
7. **Verify** monitoring shows improvement in error rates/latency
8. **Notify** team via Telegram @visionos-ops: "Rollback to revision [REVISION] completed"
9. **Document** incident in post-mortem template
10. **Create** ticket to prevent recurrence

---

## 8. Communication Templates

### Outage Notification (Users Affected)
```markdown
# Vision OS Service Incident - [DATE] [TIME] BST

We are currently experiencing an issue affecting [SPECIFIC FEATURE/SERVICE]. 
Our team is actively working to restore full functionality.

**What's affected**: 
- [List affected features, e.g., Camera streaming, AI detection, User dashboard]

**What we're doing**: 
- Investigating root cause
- Deploying fixes
- Monitoring recovery

**Expected resolution**: [TIME] BST or sooner

We apologize for the inconvenience and will provide updates every 30 minutes.
For urgent assistance, contact support@visionos.app or message @visionos_support on Telegram.

Vision OS Team
```

### Service Restored Message
```markdown
# Vision OS Service Restored - [DATE] [TIME] BST

All services are now operating normally following today's incident.

**Incident Summary**: 
- Start time: [TIME] BST
- End time: [TIME] BST  
- Duration: [DURATION]
- Root cause: [BRIEF DESCRIPTION]
- Users affected: [APPROXIMATE NUMBER]

**What we've done**: 
- [Action taken to resolve]
- [Preventive measure implemented]
- [Monitoring enhancement added]

**Next steps**: 
- Full post-mortem within 24 hours
- Service credits applied per SLA where applicable

Thank you for your patience.
Vision OS Team
```

### Scheduled Maintenance Notice
```markdown
# Upcoming Scheduled Maintenance - [DATE] [TIME] BST

To improve Vision OS performance and security, we will perform scheduled maintenance.

**Maintenance Window**: 
- Start: [DATE] [TIME] BST
- End: [DATE] [TIME] BST  
- Duration: [DURATION]

**Expected Impact**: 
- Brief interruption (< 5 minutes) to API endpoints
- No data loss
- Camera buffering will continue locally

**What to Expect**: 
- Temporary inability to access dashboard during window
- Recording continues uninterrupted
- Service auto-resumes after maintenance

We apologize for any inconvenience and appreciate your commitment to security.
Vision OS Team
```

### Data Breach Notification
```markdown
# Important Security Notice - Vision OS

**Date**: [DATE]  
**Action Required**: None - For your information only

On [DATE], we identified and resolved a security issue that may have exposed some user information.

**What happened**: 
- Unauthorized access to [DESCRIBE DATA TYPE, e.g., user email addresses, camera names]
- Issue discovered at [TIME] BST and resolved by [TIME] BST
- No payment information or video footage was accessed

**What information was involved**: 
- [List specific data elements, e.g., email addresses, phone numbers, camera location names]
- [Specify what was NOT involved, e.g., passwords, payment details, video content]

**What we're doing**: 
- Notified Bangladesh Data Protection Authority
- Contacted potentially affected users directly
- Implemented additional security measures
- Engaged third-party security firm for forensic review

**What you can do**: 
- Monitor your account for unusual activity
- Consider changing your password as a precaution (though passwords were not exposed)
- Enable two-factor authentication in your account settings

We take the security of your data seriously and sincerely regret this incident.
For questions, contact our Data Protection Officer at dpo@visionos.app.

Vision OS Team
```

---

## 9. On-Call Contacts

| Role | Name | Phone | Email | Telegram |
|------|------|-------|-------|----------|
| **Primary Engineer** | [TBD] | +880-XXX-XXXXXX | primary@visionos.app | @primary_eng |
| **Secondary Engineer** | [TBD] | +880-XXX-XXXXXX | secondary@visionos.app | @secondary_eng |
| **Firebase Support** | - | 1-800-FIREBASE | firebase-support@google.com | - |
| **Google Cloud Support** | - | +1-877-355-5787 | gcloud-support@google.com | - |
| **bKash Support** | - | 16247 | support@bkash.com | @bkash_support |
| **DPO/Legal Lead** | [TBD] | +880-XXX-XXXXXX | dpo@visionos.app | @dpo_visionos |
| **Finance Lead** | [TBD] | +880-XXX-XXXXXX | finance@visionos.app | @finance_visionos |
| **CEO/Escalation** | [TBD] | +880-XXX-XXXXXX | ceo@visionos.app | @ceo_visionos |

> **Escalation Path**: Primary → Secondary → DPO/Legal → CEO  
> **Response SLA**: Primary acknowledges within 5min, Secondary within 10min  
> **Backup**: If primary unreachable for 15min, secondary assumes primary role

---

## 10. Post-Launch Checklist (24 Hours After Launch)

> Complete all items within 24 hours after T=0 launch announcement.

- [ ] **Initial Metrics Review**: Verify day 1 metrics meet minimum thresholds (see Section 3)
- [ ] **Error Analysis**: Review all errors in Cloud Logging, create tickets for recurring issues
- [ ] **Performance Tuning**: Adjust Cloud Run CPU/memory based on actual usage patterns
- [ ] **Cost Optimization**: Review AI API usage, set budget alerts if projected >$100/day
- [ ] **Security Scan**: Run `gcloud beta scanners scan` on public endpoints
- [ ] **Backup Verification**: Confirm automated backups ran successfully during launch period
- [ ] **Log Review**: Check for any suspicious access patterns in auth logs
- [ ] **User Feedback**: Collect initial feedback from first 10 users via in-app survey
- [ ] **Documentation Update**: Update runbook with any lessons learned from launch day
- [ ] **Team Debrief**: Conduct 30-minute retrospective (scheduled for T+24hr)
- [ ] **Capacity Planning**: Review current usage vs. projections for week 2 scaling
- [ ] **SLA Compliance**: Verify uptime > 99.9% for first 24 hours
- [ ] **Payment Reconciliation**: Ensure all test bKash payments processed correctly
- [ ] **Feature Flag Audit**: Confirm all launch flags are appropriately set for steady state
- [ ] **Certificate Validation**: Ensure SSL certificates auto-renewal configured properly
- [ ] **Dependencies Check**: Update any outdated dependencies discovered during launch
- [ ] **Incident Documentation**: Complete post-mortem for any incidents that occurred
- [ ] **Customer Outreach**: Send thank-you email to first 50 users with getting started tips
- [ ] **Competitor Check**: Review any market changes or competitor announcements
- [ ] **Prepare Week 2 Plan**: Based on day 1 results, adjust growth targets and resource allocation

---
*End of Vision OS Launch Day Operations Runbook*