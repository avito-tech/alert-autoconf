import os
import xml.etree.ElementTree as etree


def get_teamcity_build_id():
    properties_path = os.getenv("TEAMCITY_BUILD_PROPERTIES_FILE")
    if properties_path is None:
        # not running in Teamcity
        return None
    path = properties_path + ".xml"
    xml_tree = etree.parse(path)
    for tag in xml_tree.getroot():
        if tag.tag == "entry" and tag.attrib.get("key") == "teamcity.build.id":
            return tag.text
    # could not find the build ID in the properties file
    return None
