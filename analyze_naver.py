# -*- coding: utf-8 -*-
import re, subprocess, json

html_file = '/tmp/naver_result.html'
with open(html_file, 'r') as f:
    html = f.read()

# Method 1: place_bluelink class
m1 = re.findall(r'place_bluelink[^>]*>([^<]+)', html)
print('=== Method 1: place_bluelink ===')
for i,n in enumerate(m1[:15]):
    print(f'  {i+1}: {n.strip()}')

# Method 2: JSON name fields
m2 = re.findall(r'"name":"([^"]+)"', html)
print('=== Method 2: JSON name fields ===')
seen = set()
for n in m2:
    if n not in seen and len(n) > 2:
        seen.add(n)
        print(f'  {n}')

# Check for our target
idx = html.find('스튜디오생일')
if idx >= 0:
    print(f'\nstudiobday found at pos {idx}')
    context = html[max(0,idx-200):idx+200]
    print(f'Context: {context[:300]}')
else:
    print('\nstudiobday NOT found')

idx2 = html.find('오늘우리')
if idx2 >= 0:
    print(f'\n오늘우리 found at pos {idx2}')
    context2 = html[max(0,idx2-200):idx2+200]
    print(f'Context: {context2[:300]}')
else:
    print('\n오늘우리 NOT found')
