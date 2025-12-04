import streamlit as st
import pandas as pd
import numpy as np

text = st.text_input(label='Message', value='Hello World!')

text2 = st.text_input(label='Message2', value=' こんにちは　世界')

text3 = st.text_input(label='Message3', value='Hello 世界!')

st.sidebar.header('サイドバー')
st.sidebar.write(text)
st.sidebar.write(text2)
st.sidebar.write(text3)


def main():
    df2 = pd.DataFrame(
        np.random.rand(20, 3),
        columns=['a', 'b', 'c']
    )

    st.line_chart(df2)
    st.area_chart(df2)
    st.bar_chart(df2)


if __name__ == '__main__':
    main()