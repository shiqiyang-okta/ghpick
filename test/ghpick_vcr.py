import vcr

gvcr = vcr.VCR(
    cassette_library_dir='fixtures/cassettes',
    record_mode='once',
    match_on=['path','method','query','body'])