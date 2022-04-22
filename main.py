import sys
import os
import re
import urllib
import http.client as httplib
import bibtexparser
from unidecode import unidecode
from bibtexparser.bwriter import BibTexWriter


# Search for the DOI given a title; e.g.  "computation in Noisy Radio Networks"
# Credit to user13348, slight modifications
# http://tex.stackexchange.com/questions/6810/automatically-adding-doi-fields-to-a-hand-made-bibliography
def searchdoi(title, author):
    params = urllib.parse.urlencode({"titlesearch": "titlesearch", "auth2": author, "atitle2": title, "multi_hit": "on",
                                     "article_title_search": "Search", "queryType": "author-title"})
    headers = {"User-Agent": "Mozilla/5.0", "Accept": "text/html", "Content-Type": "application/x-www-form-urlencoded",
               "Host": "www.crossref.org"}
    # conn = httplib.HTTPConnection("www.crossref.org:80") # Not working any more, HTTPS required
    conn = httplib.HTTPSConnection("www.crossref.org")
    conn.request("POST", "/guestquery/", params, headers)
    response = conn.getresponse()
    # print(response.status, response.reason)
    data = response.read()
    conn.close()
    return re.search(r'doi\.org/([^"^<>]+)', str(data))


def normalize(string):
    """Normalize strings to ascii, without latex."""
    string = re.sub(r'[{}\\\'"^]', "", string)
    string = re.sub(r"\$.*?\$", "", string)  # better remove all math expressions
    return unidecode(string)


def get_authors_plain(authors):
    return [author.strip() for author in normalize(authors).split("and")]


def get_authors(entry):
    """Get a list of authors' or editors' last names."""

    def get_last_name(authors):
        for author in authors:
            if "," in author:
                yield author.split(",")[0]
            elif " " in author:
                yield author.split(" ")[-1]
            else:
                yield author

    try:
        authors = entry["author"]
    except KeyError:
        authors = entry["editor"]

    authors = get_authors_plain(authors)
    return list(get_last_name(authors))


def load_from_bibtex(filename):
    print("Reading Bibliography...")
    with open(filename) as bibtex_file:
        bibliography = bibtexparser.load(bibtex_file)
    return bibliography


def add_doi_to_all_entries_in_file(bibliography):
    print("Looking for Dois...")
    before = 0
    new = 0
    total = len(bibliography.entries)
    for i, entry in enumerate(bibliography.entries):
        print("\r{i}/{total} entries processed, please wait...".format(i=i, total=total), flush=True, end="")
        try:
            if "doi" not in entry or entry["doi"].isspace():
                title = entry["title"]
                authors = get_authors(entry)
                for author in authors:
                    doi_match = searchdoi(title, author)
                    if doi_match:
                        doi = doi_match.groups()[0]
                        entry["doi"] = doi
                        new += 1
            else:
                before += 1
        except:
            pass
    template = "We added {new} DOIs !\nBefore: {before}/{total} entries had DOI\nNow: {after}/{total} entries have DOI"
    print(template.format(new=new, before=before, after=before + new, total=total))

    return bibliography


def save_as_bibtex(bibliography):
    outfile = filename + "_doi.bib"
    print("Writing result to ", outfile)
    writer = BibTexWriter()
    writer.indent = ' ' * 4  # indent entries with 4 spaces instead of one
    with open(outfile, 'w') as bibfile:
        bibfile.write(writer.write(bibliography))


def save_as_ifmo(filename, bibliography):
    # see https://ntv.ifmo.ru/ru/stat/146/
    def shortify_authors(authors):
        for author in authors:
            if ',' in author:
                last, _, first = author.partition(', ')
            elif ' ' in author:
                first, _, last = author.partition(' ')
            else:
                raise NotImplemented
            short_first = re.sub(r"[a-z]+", ".", first)
            yield f"{last} {short_first}"
    def find_where_published(entry):
        entry_type = entry["ENTRYTYPE"]
        if entry_type == "article":
            return f"{entry['journal']}. {entry['year']}. V. {entry['volume']}. N {entry['number']}. P. {entry['pages']}."
        elif entry_type == "inproceedings":
            return f"{entry['booktitle']}. {entry['address']}, {entry['year']}. P. {entry['pages']}."
        else:
            print(f"ERROR: unknown entry type {entry_type}; skipping {entry}")
    def get_doi_if_exists(entry):
        doi = entry.get("doi")
        if not doi:
            return ""
        doi = urllib.parse.urlparse(doi).path[1:] if "doi.org" in doi else doi
        return f" doi: {doi}"
    """Donatelli M., Estatico C., Martinelli A., Serra-Capizzano S. Improved image deblurring with anti-reflective
    boundary conditions and re-blurring // Inverse Problems. 2006. V. 22. N 6. P. 2035–2053.

    Mirkin B., Gutman P.-O. Lyapunov-based adaptive output-feedback control of MIMO nonlinear plants with unknown,
    time-varying state delays // Proc. 9th IFAC Workshop on Time Delay Systems. Prague, Czech Republic, 2010. Part. 1. P. 33–38."""
    output = []
    for entry in bibliography.entries:
        authors = ', '.join(shortify_authors(get_authors_plain(entry["author"])))
        where_published = find_where_published(entry)
        doi = get_doi_if_exists(entry)
        template = f"{authors} {entry['title']} // {where_published}{doi}{os.linesep}"
        output.append(template)
    output_name = filename + ".ifmo.txt"
    with open(output_name, 'w') as file:
        file.writelines(output)
    print("Output is saved to:", output_name)


if __name__ == "__main__":
    filename = sys.argv[1]
    bibliography = load_from_bibtex(filename)
    bibliography = add_doi_to_all_entries_in_file(bibliography)
    save_as_ifmo(filename, bibliography)
