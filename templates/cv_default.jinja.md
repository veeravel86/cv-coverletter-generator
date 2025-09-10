# {{ name }}

{% if contact_info %}
## CONTACT INFORMATION
{% if style.contact_format == "horizontal" %}
{{ contact_info.email }} {{ style.bullet_style }} {{ contact_info.phone }} {{ style.bullet_style }} {{ contact_info.location }}{% if contact_info.linkedin %} {{ style.bullet_style }} {{ contact_info.linkedin }}{% endif %}
{% else %}
**Email:** {{ contact_info.email }}
**Phone:** {{ contact_info.phone }}
**Location:** {{ contact_info.location }}
{% if contact_info.linkedin %}**LinkedIn:** {{ contact_info.linkedin }}{% endif %}
{% endif %}
{% endif %}

{% if career_summary %}
## CAREER SUMMARY
{{ career_summary }}
{% endif %}

{% if skills %}
## SKILLS
{% for skill in skills %}
{{ style.bullet_style }} {{ skill }}
{% endfor %}
{% endif %}

{% if experience %}
## EXPERIENCE
{% for job in experience %}
**{{ job.title }}** | {{ job.company }} | {{ job.dates }}

{% for bullet in job.bullets %}
{{ style.bullet_style }} {{ bullet }}
{% endfor %}

{% endfor %}
{% endif %}

{% if education %}
## EDUCATION
{% for edu in education %}
**{{ edu.degree }}** | {{ edu.institution }} | {{ edu.year }}
{% if edu.details %}{{ edu.details }}{% endif %}

{% endfor %}
{% endif %}

{% if certifications %}
## CERTIFICATIONS
{% for cert in certifications %}
{{ style.bullet_style }} {{ cert }}
{% endfor %}
{% endif %}