"""Construction query vocabulary. Preview and execution use the same deterministic bank."""
from .providers import clean

TRADES = {
    'construction': ('All construction contractors', 'construction contractor', 'construction workers', 'construction'),
    'general': ('General contractors', 'general contractor', 'superintendents', 'commercial construction'),
    'roofing': ('Roofing contractors', 'roofing contractor', 'roofers', 'commercial roofing'),
    'electrical': ('Electrical contractors', 'electrical contractor', 'electricians', 'electrical construction'),
    'mechanical': ('Mechanical / HVAC contractors', 'mechanical contractor', 'HVAC installers', 'mechanical construction'),
    'plumbing': ('Plumbing contractors', 'plumbing contractor', 'plumbers', 'commercial plumbing'),
    'concrete': ('Concrete contractors', 'concrete contractor', 'concrete finishers', 'concrete construction'),
    'civil': ('Civil / excavation contractors', 'civil contractor', 'equipment operators', 'civil construction'),
    'drywall': ('Drywall / framing contractors', 'drywall contractor', 'drywall installers', 'drywall framing'),
}
SIGNALS = {'hiring':'Hiring / recruiting', 'award':'Contract / project awards',
           'mobilization':'Starting construction', 'expansion':'Expansion / new facilities'}

# Ranked from the 2026-10-14 DFW pilot. These are evidence-backed starting terms,
# not a permanent claim about every provider, location or future index state.
TOP_15 = [
    ('award', '{trade} "awarded contract" construction', ()),
    ('award', '"selected as general contractor" {specialty}', ()),
    ('award', '{trade} "notice of award" construction', ()),
    ('award', '{trade} "contract award" project', ()),
    ('award', '{trade} "secured" "construction contract"', ()),
    ('mobilization', '{trade} "breaks ground" construction project', ()),
    ('mobilization', '{trade} "starts work" new facility', ()),
    ('mobilization', '"construction underway" {trade}', ()),
    ('mobilization', '{trade} "notice to proceed" construction', ()),
    ('mobilization', '{trade} contractor project start', ('constructiondive.com','enr.com')),
    ('mobilization', '{trade} "begins construction" contractor', ('communityimpact.com','rebusinessonline.com')),
    ('expansion', '{trade} "expanding operations" new facility', ()),
    ('expansion', '{trade} "opens new" branch headquarters', ()),
    ('hiring', '{trade} "hiring multiple positions" field crews', ()),
    ('hiring', '{trade} "job fair" "field" hiring', ()),
]

EXCLUDED_JOB_DOMAINS = [
    'facebook.com','linkedin.com','indeed.com','instagram.com','ziprecruiter.com',
    'hiringcafe.com','glassdoor.com','monster.com','careerbuilder.com',
]

# Each signal has 20 distinct intents, not numbered copies of one broad query.
TEMPLATES = {
    'hiring': [
        '{trade} hiring {workers}', '{trade} "job openings"',
        '{specialty} "join our team"', '{trade} recruiting field crews',
        '{trade} hiring apprentices', '{trade} hiring foreman',
        '{trade} hiring project managers', '{trade} hiring estimators',
        '{trade} hiring safety manager', '{trade} hiring site supervisors',
        '{workers} "now hiring" contractor', '{trade} expanding workforce hiring',
        '{trade} hiring multiple positions', '{trade} hiring event job fair',
        '{specialty} crews needed new project', '{trade} careers open positions',
        '{trade} paid apprenticeship applications', '{workers} recruitment construction projects',
        '{trade} hiring full time field staff', '{trade} new project staffing announcement',
    ],
    'award': [
        '{trade} awarded construction contract', '{trade} selected for new project',
        '{specialty} contract award announcement', '{trade} awarded school project',
        '{trade} awarded hospital project', '{trade} awarded warehouse project',
        '{trade} awarded municipal contract', '{trade} awarded multifamily project',
        '{trade} awarded industrial facility project', '{trade} awarded renovation contract',
        '{trade} named contractor project announcement', '{specialty} winning bidder contract award',
        '{trade} city council contract award', '{trade} school board contract approval',
        '{trade} notice of award construction', '{trade} secured new construction contract',
        '{trade} selected subcontractor project', '{specialty} awarded commercial project',
        '{trade} awarded university construction contract', '{trade} awarded public works contract',
    ],
    'mobilization': [
        '{trade} groundbreaking new project', '{trade} construction starts this month',
        '{specialty} project mobilization', '{trade} breaking ground school',
        '{trade} breaking ground hospital', '{trade} warehouse construction begins',
        '{trade} municipal project construction begins', '{trade} multifamily construction starts',
        '{trade} industrial project construction begins', '{trade} renovation work begins',
        '{trade} crews mobilizing jobsite', '{trade} notice to proceed construction',
        '{specialty} project kickoff announcement', '{trade} site preparation begins',
        '{trade} crews begin installation project', '{specialty} construction phase begins',
        '{trade} project underway announcement', '{trade} starts work new facility',
        '{trade} university project groundbreaking', '{trade} public works project starts',
    ],
    'expansion': [
        '{trade} expanding new office', '{trade} opens new branch',
        '{specialty} company expansion announcement', '{trade} opens new headquarters',
        '{trade} opens new warehouse', '{trade} expands service area',
        '{trade} new regional office', '{trade} new fabrication facility',
        '{trade} expanding operations hiring', '{trade} launches new division',
        '{trade} opens new training center', '{trade} adds new field crews',
        '{trade} acquires local contractor expansion', '{trade} announces merger growth',
        '{trade} relocates larger facility', '{trade} new equipment yard',
        '{trade} opens second location', '{trade} expansion ribbon cutting',
        '{trade} new market expansion', '{trade} facility expansion investment',
    ],
}


def query_bank(trade='construction', location='Dallas Fort Worth Texas', signal='hiring', terms=''):
    if trade not in TRADES or signal not in (*SIGNALS, 'all'):
        raise ValueError('Choose a supported construction trade and signal')
    location = clean(location, 100)
    terms = clean(terms, 300) if terms.strip() else ''
    label, keyword, workers, specialty = TRADES[trade]
    normalized = ''.join(c for c in location.lower() if c.isalnum())
    places = (['Dallas Texas', '"Fort Worth" Texas', 'Arlington Texas', 'Plano Texas', 'Denton Texas']
              if normalized in ('dfw', 'dallasfortworth', 'dallasfortworthtexas', 'dallasfortworthtx') else [location])
    signals = list(SIGNALS) if signal == 'all' else [signal]
    rows = []
    for index in range(20):
        for kind in signals:
            phrase = TEMPLATES[kind][index].format(trade=keyword, workers=workers, specialty=specialty)
            rows.append({'id': f'{trade}:{kind}:{index}', 'signal': kind, 'trade': label,
                         'query': f'{phrase} {places[index % len(places)]} {terms}'.strip()})
    return rows


def tested_top_queries(trade='construction', location='Dallas Fort Worth Texas', terms=''):
    if trade not in TRADES:
        raise ValueError('Choose a supported construction trade')
    location = clean(location, 100)
    terms = clean(terms, 300) if terms.strip() else ''
    label, keyword, workers, specialty = TRADES[trade]
    normalized = ''.join(c for c in location.lower() if c.isalnum())
    place = '"Dallas Fort Worth" Texas' if normalized in (
        'dfw', 'dallasfortworth', 'dallasfortworthtexas', 'dallasfortworthtx') else location
    rows=[]
    for index,(signal,template,domains) in enumerate(TOP_15):
        phrase=template.format(trade=keyword,workers=workers,specialty=specialty,place=place)
        if '{place}' not in template:
            phrase=f'{phrase} {place}'
        rows.append({'id':f'best:{trade}:{index}','signal':signal,'trade':label,
                     'query':f'{phrase} {terms}'.strip(),'tested_rank':index+1,
                     'include_domains':list(domains)})
    return rows


def search_request(query, period, include_domains=()):
    if period not in ('week', 'month', 'year'):
        raise ValueError('Choose a supported search window')
    request=dict(query=query, search_depth='basic', auto_parameters=False, max_results=10,
                topic='general', time_range=period, include_answer=False, include_raw_content=False,
                include_usage=True, include_published_date=True)
    if include_domains:
        request['include_domains']=list(include_domains)
        request['include_domains_mode']='restrict'
    else:
        request['exclude_domains']=list(EXCLUDED_JOB_DOMAINS)
    return request


def selected_plan(trade, location, signal, terms, period, selected, query_set='tested'):
    if not 1 <= len(selected) <= 10 or len(set(selected)) != len(selected):
        raise ValueError('Select between 1 and 10 different queries for one run')
    if query_set not in ('tested','full'):
        raise ValueError('Choose a supported query set')
    rows=(tested_top_queries(trade,location,terms) if query_set=='tested'
          else query_bank(trade, location, signal, terms))
    bank = {r['id']: r for r in rows}
    if any(ident not in bank for ident in selected):
        raise ValueError('Query selection no longer matches the filters. Rebuild the query list.')
    return [search_request(bank[ident]['query'], period,bank[ident].get('include_domains',())) for ident in selected]
