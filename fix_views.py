import re
with open('products/views.py', 'r') as f:
    text = f.read()

text = re.sub(r'# --- 4\. Order & Cart Processing\n# --- 4\. Order  \(with Razorpay\) --- Cart Processing \(with Razorpay\) ---', '# --- 4. Order & Cart Processing (with Razorpay) ---', text)
# Just in case, let's fix it by regex looking for the messed up lines
text = text.replace('# --- 4. Order & Cart Processing\n# --- 4. Order  (with Razorpay) --- Cart Processing (with Razorpay) ---', '# --- 4. Order & Cart Processing (with Razorpay) ---')
text = text.replace('# --- 4. Order & Cart Processing\n (with Razorpay) ---', '# --- 4. Order & Cart Processing (with Razorpay) ---')

with open('products/views.py', 'w') as f:
    f.write(text)
