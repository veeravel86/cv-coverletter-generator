# {{ contact.name }}

📧 {{ contact.email }} | 📞 {{ contact.phone }} | 📍 {{ contact.location }}{% if contact.linkedin %} | 🔗 [LinkedIn]({{ contact.linkedin }}){% endif %}{% if contact.website %} | 🌐 [Website]({{ contact.website }}){% endif %}

---

## **PROFESSIONAL SUMMARY**

{{ professional_summary }}

---

## **CORE SKILLS**

{% for skill in skills %}**{{ skill }}**{% if not loop.last %} | {% endif %}{% endfor %}

---

## **PROFESSIONAL EXPERIENCE**

### **{{ current_role.position_name }}** | {{ current_role.company_name }}, {{ current_role.location }} | {{ current_role.start_date }} - {{ current_role.end_date }} ({{ current_role.work_duration }})

{% for bullet in current_role.key_bullets %}• {{ bullet }}
{% endfor %}
{% if previous_roles %}
{% for role in previous_roles %}
### **{{ role.position_name }}** | {{ role.company_name }}, {{ role.location }} | {{ role.start_date }} - {{ role.end_date }} ({{ role.work_duration }})

{% for bullet in role.key_bullets %}• {{ bullet }}
{% endfor %}
{% endfor %}
{% endif %}
{% if additional_info %}

---

## **ADDITIONAL INFORMATION**

{{ additional_info }}
{% endif %}

---

*Generated at: {{ generated_at }}*