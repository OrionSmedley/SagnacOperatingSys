# %%
from clerk import hysteresis, Counter

# %%
hysteresis( [1,2,3,4,5])



# %% 
counter(4)
counter.cnt

# %%
c1 = Counter()
c2 = Counter()

# %%
c1(4)
c2(3)

print(c1.cnt)
print(c2.cnt)
# %%
def counter(numSweeps): counter.cnt = (counter.cnt +1) % numSweeps
def counter2(numSweeps): counter2.cnt = (counter2.cnt +1) % numSweeps