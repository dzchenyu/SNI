import seaborn as sns
import matplotlib.pyplot as plt
import pandas as pd
# 示例数据
data = {'A': [1, 2, 3, 4, 5], 'B': [5, 4, 3, 2, 1]}
df = pd.DataFrame(data)
# 绘制散点图
sns.scatterplot(x='A', y='B', data=df)
plt.title("散点图示例")
plt.show()