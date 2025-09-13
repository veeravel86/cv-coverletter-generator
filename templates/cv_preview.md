# {{ contact.name }}

📧 {{ contact.email }} | 📞 {{ contact.phone }} | 📍 {{ contact.location }}{% if contact.linkedin %} | 🔗 [LinkedIn]({{ contact.linkedin }}){% endif %}{% if contact.website %} | 🌐 [Website]({{ contact.website }}){% endif %}

---

## **PROFESSIONAL SUMMARY**

{{ professional_summary }}

---

## **CORE SKILLS**

<div class="core-skills">{% for skill in skills %}<span class="skill-tag">{{ skill }}</span>{% endfor %}</div>

---

## **PROFESSIONAL EXPERIENCE**

### **{{ current_role.job_title }}** | {{ current_role.company }}, {{ current_role.location }} | {{ current_role.start_date }} - {{ current_role.end_date }}

{% for bullet in current_role.bullets %}• {{ bullet.to_formatted_string() }}
{% endfor %}
{% if previous_roles %}
{% for role in previous_roles %}
### **{{ role.job_title }}** | {{ role.company }}, {{ role.location }} | {{ role.start_date }} - {{ role.end_date }}

{% for bullet in role.bullets %}• {{ bullet.to_formatted_string() }}
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