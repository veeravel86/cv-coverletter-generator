# {{ name }}

<div style="display: flex; justify-content: space-between;">
<div style="width: 65%;">

{% if career_summary %}
## CAREER SUMMARY
{{ career_summary }}
{% endif %}

{% if experience %}
## EXPERIENCE
{% for job in experience %}
**{{ job.title }}** | {{ job.company }}  
*{{ job.dates }}*

{% for bullet in job.bullets %}
{{ style.bullet_style }} {{ bullet }}
{% endfor %}

{% endfor %}
{% endif %}

</div>
<div style="width: 30%;">

{% if contact_info %}
## CONTACT
**{{ contact_info.email }}**  
{{ contact_info.phone }}  
{{ contact_info.location }}  
{% if contact_info.linkedin %}{{ contact_info.linkedin }}{% endif %}
{% endif %}

{% if skills %}
## SKILLS
{% for skill in skills %}
{{ style.bullet_style }} {{ skill }}
{% endfor %}
{% endif %}

{% if education %}
## EDUCATION
{% for edu in education %}
**{{ edu.degree }}**  
{{ edu.institution }}  
{{ edu.year }}
{% if edu.details %}{{ edu.details }}{% endif %}

{% endfor %}
{% endif %}

{% if certifications %}
## CERTIFICATIONS
{% for cert in certifications %}
{{ style.bullet_style }} {{ cert }}
{% endfor %}
{% endif %}

</div>
</div>