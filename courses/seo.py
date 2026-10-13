"""schema.org JSON-LD for search engines (Course, Organization, BreadcrumbList)."""

import json

from django.conf import settings

_MODE = {"in_person": "onsite", "online": "online", "hybrid": "blended"}


def dumps(data):
    """Serialise for an inline <script type="application/ld+json">: '<' is escaped so content can't close the tag."""
    return json.dumps(data, ensure_ascii=False).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")


def _abs(request, path):
    return request.build_absolute_uri(path)


def organization(request, name):
    return {"@type": "EducationalOrganization", "name": name, "url": _abs(request, "/")}


def breadcrumbs(request, trail):
    return {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": i, "name": label, "item": _abs(request, url)}
        for i, (label, url) in enumerate(trail, 1)]}


def website(request, name):
    return {"@context": "https://schema.org", "@type": "WebSite", "name": name, "url": _abs(request, "/"),
            "inLanguage": "fa", "potentialAction": {
                "@type": "SearchAction", "target": _abs(request, "/courses/") + "?q={search_term_string}",
                "query-input": "required name=search_term_string"}}


def course(request, course, org_name):
    data = {
        "@context": "https://schema.org", "@type": "Course", "name": course.title,
        "description": course.meta_description or course.summary, "inLanguage": "fa",
        "url": _abs(request, course.get_absolute_url()), "provider": organization(request, org_name),
        "educationalLevel": course.get_level_display(), "courseCode": course.slug,
    }
    if course.cover:
        data["image"] = _abs(request, course.cover.url)
    if course.prerequisites:
        data["coursePrerequisites"] = course.prerequisites
    # Fees are stored in toman; schema.org wants an ISO 4217 code, so convert to rial (1 toman = 10 rial).
    data["offers"] = {"@type": "Offer", "price": str(course.price * 10), "priceCurrency": "IRR",
                      "category": "Paid" if course.price else "Free", "url": data["url"],
                      "availability": "https://schema.org/InStock" if course.next_batch else "https://schema.org/PreOrder"}
    instances = []
    for batch in course.batches.all():
        if not batch.is_open:
            continue
        instance = {"@type": "CourseInstance", "courseMode": _MODE.get(batch.mode, "onsite"),
                    "startDate": batch.start_date.isoformat()}
        if course.duration_hours:
            instance["courseWorkload"] = f"PT{course.duration_hours}H"
        if course.instructor:
            instance["instructor"] = {"@type": "Person", "name": course.instructor.display_name}
        instances.append(instance)
    if instances:
        data["hasCourseInstance"] = instances
    reviews = course.approved_reviews
    if reviews:
        data["aggregateRating"] = {"@type": "AggregateRating", "ratingValue": course.rating,
                                   "reviewCount": len(reviews), "bestRating": 5, "worstRating": 1}
    return data
