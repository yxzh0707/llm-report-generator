"""Explicit decimal normalization; unknown request wording is not guessed.

The automatic recognizer supports a narrow English quarterly-input contract.
Other tasks can declare normalization on individual calculator facts. Neither
path verifies the source value or performs currency conversion.
"""
from decimal import Decimal, ROUND_HALF_UP, localcontext
import re

PLACES = {'zero': 0, 'one': 1, 'two': 2, 'three': 3, 'four': 4,
          'five': 5, 'six': 6, 'seven': 7, 'eight': 8}
SCALES = {'': 0, 'thousand': 3, 'million': 6, 'billion': 9, 'trillion': 12}


def presentation_policy(task):
    """Recognize an explicit, unambiguous currency display contract.

    Presentation alone never authorizes rounding the arithmetic inputs.
    Conflicting or negated instructions are left unrecognized.
    """
    number = r'(zero|one|two|three|four|five|six|seven|eight|[0-8])'
    unit = r'(USD|EUR|GBP|JPY|CNY|CAD|AUD)\s+(thousand|million|billion|trillion)s?'
    specs = set()
    for sentence in re.split(r'[.;\n]', task):
        if re.search(r"\b(?:not|never|don't|without)\b", sentence, re.I):
            continue
        for pattern, reverse in [(unit+r'\s+to\s+'+number+r'\s+decimal places?\b', False),
                                 (number+r'\s+decimal(?: places?)?\s+'+unit, True)]:
            for match in re.finditer(pattern, sentence, re.I):
                n, currency, scale = (match[1],match[2],match[3]) if reverse else (match[3],match[1],match[2])
                specs.add((currency.upper()+' '+scale.lower()+'s', PLACES.get(n.lower(), int(n) if n.isdigit() else None)))
    if len(specs) != 1:
        return {}
    unit, places = specs.pop()
    return dict(unit=unit, decimal_places=places)


def input_precision_policy(task):
    # Require both explicit rounding and explicit use of displayed quarterly
    # inputs. Presentation-only rounding must not change calculation inputs.
    sentences = re.split(r'[.;\n]', task)
    rounding = []
    basis = []
    for sentence in sentences:
        if re.search(r"\b(?:not|never|don't|without)\b", sentence, re.I):
            continue
        match = re.fullmatch(r'\s*Round each to (zero|one|two|three|four|five|six|seven|eight|[0-8]) decimal(?: places?)? (USD|EUR|GBP|JPY|CNY|CAD|AUD) (thousand|million|billion|trillion)s?\b[^.]*', sentence, re.I)
        if match:
            n = match[1].lower()
            rounding.append(dict(unit=match[2].upper() + ' ' + match[3].lower() + 's', decimal_places=PLACES[n] if n in PLACES else int(n)))
        if re.fullmatch(r'\s*Use the displayed (?:[a-z0-9]+[- ]decimal|rounded) quarterly amounts for all calculations\s*', sentence, re.I):
            basis.append(sentence.strip())
    if len(rounding) == 1 and len(basis) == 1:
        return dict(**rounding[0], scope='fiscal_quarter_facts', origin='explicit_user_request', matched_basis=basis[0])
    # A common equivalent request: display quarterly amounts to a stated
    # precision, then calculate a sum from those displayed quarters.
    display = presentation_policy(task)
    for sentence in sentences:
        if re.search(r"\b(?:not|never|don't|without)\b", sentence, re.I):
            continue
        match = re.search(r'\bsum of the displayed Q[1-4] and Q[1-4] (?:values|amounts)\b', sentence, re.I)
        if display and match:
            return dict(**display, scope='displayed_quarter_sum', quarters=re.findall(r'Q[1-4]',match[0],re.I),
                        origin='explicit_user_request', matched_basis=match[0])
    return {}


def unit_scale(unit):
    match = re.fullmatch(r'(USD|EUR|GBP|JPY|CNY|CAD|AUD)(?:\s+(thousand|million|billion|trillion)s?)?', unit.strip(), re.I)
    if not match:
        raise ValueError('Normalization supports explicit currency codes and thousand/million/billion/trillion scales only')
    return match[1].upper(), SCALES[(match[2] or '').lower()]


def normalize(value, source_unit, specification):
    if not isinstance(specification, dict) or set(specification) != {'unit', 'decimal_places'}:
        raise ValueError('normalization requires unit and decimal_places only')
    places = specification['decimal_places']
    if type(places) is not int or not 0 <= places <= 8 or not isinstance(specification['unit'], str):
        raise ValueError('Normalization decimal_places must be 0–8 and unit must be text')
    currency, scale = unit_scale(source_unit)
    target_currency, target_scale = unit_scale(specification['unit'])
    if currency != target_currency:
        raise ValueError('Normalization cannot convert currencies')
    if value is None:
        return None
    with localcontext() as ctx:
        ctx.prec = 80
        number = (Decimal(value) * Decimal(10) ** (scale - target_scale)).quantize(
            Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP)
        return format(abs(number) if number == 0 else number, 'f')
