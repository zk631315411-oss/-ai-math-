# 第2章行列式

许多问题需要直接从线性方程组的系数和常数项判断它有没有解，有多少解。本章对方程个数与未知量个数相等的线性方程组讨论这个问题。

先研究两个方程的二元一次方程组

$$
\left\{ \begin{array}{l} a _ {1 1} x _ {1} + a _ {1 2} x _ {2} = b _ {1}, \\ a _ {2 1} x _ {1} + a _ {2 2} x _ {2} = b _ {2}, \end{array} \right. \tag {1}
$$

其中  $a_{11}, a_{21}$  不全为 0, 不妨设  $a_{11} \neq 0$ , 把它的增广矩阵经过初等行变换化成阶梯形矩阵:

$$
\left( \begin{array}{l l l} a _ {1 1} & a _ {1 2} & b _ {1} \\ a _ {2 1} & a _ {2 2} & b _ {2} \end{array} \right) \xrightarrow {\text {(2)} + \text {(1)} \cdot \left(- \frac {a _ {2 1}}{a _ {1 1}}\right)} \left( \begin{array}{c c c} a _ {1 1} & a _ {1 2} & b _ {1} \\ 0 & a _ {2 2} - \frac {a _ {2 1}}{a _ {1 1}} a _ {2 2} & b _ {2} - \frac {a _ {2 1}}{a _ {1 1}} b _ {1} \end{array} \right).
$$

情形1  $a_{11}a_{22} - a_{12}a_{21}\neq 0$  ，此时原方程组有唯一解：

$$
\left(\frac {b _ {1} a _ {2 2} - b _ {2} a _ {1 2}}{a _ {1 1} a _ {2 2} - a _ {1 2} a _ {2 1}}, \frac {a _ {1 1} b _ {2} - a _ {2 1} b _ {1}}{a _ {1 1} a _ {2 2} - a _ {1 2} a _ {2 1}}\right).
$$

情形2  $a_{11}a_{22} - a_{12}a_{21} = 0$  ，此时原方程组无解或者有无穷多个解。

为了便于记忆表达式  $a_{11}a_{22} - a_{12}a_{21}$  ，把它记成

$$
\left| \begin{array}{l l} a _ {1 1} & a _ {1 2} \\ a _ {2 1} & a _ {2 2} \end{array} \right| = a _ {1 1} a _ {2 2} - a _ {1 2} a _ {2 1}. \tag {2}
$$

这个表达式称为2阶行列式。它是二元一次方程组(1)的系数矩阵

$$
A = \left( \begin{array}{l l} a _ {1 1} & a _ {1 2} \\ a _ {2 1} & a _ {2 2} \end{array} \right) \tag {3}
$$

中, 主对角线上两个元素的乘积  $a_{11}a_{22}$  减去反对角线上两个元素的乘积  $a_{12}a_{21}$  所得的表达式。因此也称这个表达式是 2 级矩阵  $A$  的行列式, 简洁地记作  $|A|$ , 或者  $\det A$  。

利用2阶行列式的概念，可以把上述结论叙述成：

##### 命题1
命题1 两个方程的二元一次方程组(1)有唯一解的充分必要条件是：它的系数矩阵  $A$  的行列式（简称为系数行列式）  $|A| \neq 0$  ，此时它的唯一解是：

$$
\left[ \begin{array}{c c} \left| \begin{array}{l l} b _ {1} & a _ {1 2} \\ b _ {2} & a _ {2 2} \end{array} \right|, & \left| \begin{array}{l l} a _ {1 1} & b _ {1} \\ a _ {2 1} & b _ {2} \end{array} \right| \\ \hline a _ {1 1} & a _ {1 2} \\ a _ {2 1} & a _ {2 2} \end{array} , \quad \frac {\left| \begin{array}{l l} a _ {1 1} & b _ {1} \\ a _ {2 1} & b _ {2} \end{array} \right|}{\left| \begin{array}{l l} a _ {1 1} & a _ {1 2} \\ a _ {2 1} & a _ {2 2} \end{array} \right|}. \right]. \tag {4}
$$

对于数域  $K$  上  $n$  个方程的  $n$  元线性方程组有没有类似的结论？这需要用到  $n$  阶行列式的概念。本章就来介绍  $n$  阶行列式的概念和性质，并回答上述问题。行列式在几何、分析等数学分支中也有重要应用。

## 2.1  $\pmb{n}$  元排列

### 2.1.1 内容精华

从2阶行列式的定义可知，它是由两项组成的表达式：  $a_{11}a_{22} - a_{12}a_{21}$  ，一项带正号，另一项带负号，如何决定这符号？观察这两项的区别仅在于列指标的排列不同，一个是12，另一个是21。由此可知，为了给出  $\pmb{n}$  阶行列式的概念，需要首先讨论  $\pmb{n}$  个自然数组成的全排列的性质。

$n$  个不同的自然数的一个全排列称为一个  $\pmb{n}$  元排列。

例如，自然数1,2,3形成的3元排列有

$$
1 2 3, 1 3 2, 2 1 3, 2 3 1, 3 1 2, 3 2 1.
$$

给定  $n$  个不同的自然数, 它们形成的全排列有  $n!$  个。因此对于给定的  $n$  个不同的自然数,  $n$  元排列的总数是  $n!$  。

我们在大多数情形下，考虑的是自然数  $1,2\cdots,n$  形成的  $n$  元排列，在某些情形下也需要考虑某  $n$  个不同的自然数形成的  $n$  元排列。下面讨论的  $n$  元排列的性质，如果没有特别声明，考虑的是  $1,2,\dots,n$  形成的  $n$  元排列，但对任意  $n$  个不同的自然数形成的  $n$  元排列也成立。

4元排列2341中，2与3形成的数对23，小的数在前，大的数在后，此时称这一对数构成一个顺序；而2与1形成的数对21，大的数在前，小的数在后，此时称这一对数构成一个逆序。排列2341中，构成逆序的数对有21,31,41，共3对，此时我们称排列2341的逆序数是3，记作  $\tau(2341) = 3$  。

在  $n$  元排列  $a_{1}a_{2}\dots a_{n}$  中，任取一对数  $a_{i}a_{j}$  （其中  $i < j$ ），如果  $a_{i} < a_{j}$ ，那么称这一对数构成一个顺序；如果  $a_{i} > a_{j}$ ，那么称这一对数构成一个逆序。一个  $n$  元排列中逆序的总数称为逆序数，记作  $\tau(a_{1}a_{2}\dots a_{n})$ 。

4元排列2143中，构成逆序的数对有21,43，共2对。于是

$$
\tau (2 1 4 3) = 2.
$$

逆序数为奇数的排列称为奇排列，逆序数为偶数的排列称为偶排列。

上述例子中，2341是奇排列，2143是偶排列。

把排列2341的3和1互换位置，其余数不动，便得到排列2143。像这样的变换称为一个对换，记作(3,1)。对换的概念也适用于  $n$  元排列。

奇排列2341经过对换(3,1)变成的排列2143是偶排列。由此猜想有下述结论：

##### 定理1
定理1 对换改变  $n$  元排列的奇偶性。

证明 先看对换的两个数在  $n$  元排列中相邻的情形：

$$
\begin{array}{l} \dots \dots i j \dots \dots (I) \\ \downarrow (i, j) \\ \dots \dots j \quad i \dots \dots (Ⅱ) \\ \end{array}
$$

$i$  和  $j$  以外的数构成的数对是顺序还是逆序，在（I）与（Ⅱ）中是一样的； $i$  和  $j$  以外的数与  $i$  （或  $j$  )构成的数对是顺序还是逆序，在（I)与（Ⅱ）中也是一样的。只有数对  $ij$  ，如果它在(I)中是顺序，那么它在(Ⅱ)中是逆序；如果它在(I)中是逆序，那么它在(Ⅱ)中是逆序，那么它在(Ⅱ)中是顺序。前一情形，（Ⅱ）比(I)多一个逆序；后一情形，（Ⅱ）比(I)少一个逆序。因此(I)与（Ⅱ）的奇偶性相反。

再看一般情形：

$$
\begin{array}{l} \dots \dots i k _ {1} \dots k _ {s} j \dots \dots (Ⅲ) \\ \downarrow (i, j) \\ \dots \dots j k _ {1} \dots k _ {s} i \dots \dots (IV) \\ \end{array}
$$

从（Ⅲ）变成（IV）可以经过下列相邻两数的对换来实现：

$$
(i, k _ {1}), \dots , (i, k _ {s}), (i, j), (k _ {s}, j), \dots , (k _ {1}, j).
$$

这一共作了  $s + 1 + s = 2s + 1$  次相邻两数的对换。由于奇数次相邻两数的对换会改变排列的奇偶性，因此（Ⅲ）与（IV）的奇偶性相反。

有时需要把一个  $n$  元排列经过若干次对换变成自然序数列  $123 \cdots n$  。这是否总能办到？先看一个5元排列的例子：

$$
3 4 5 2 1 \xrightarrow {(5 , 1)} 3 4 1 2 5 \xrightarrow {(4 , 2)} 3 2 1 4 5 \xrightarrow {(3 , 1)} 1 2 3 4 5.
$$

上述过程的第1步是作一个对换，把5换到最后的位置；第2步作一个对换，把4放到倒数第2个位置；依次类推。显然这一方法对于任何一个  $n$  元排列也适用。这就肯定地回答了上述问题。

进一步我们看到把排列34521变成12345共作了3次对换，而  $\tau(34521) = 7$  。这表明在这个例子中，所作对换的次数与原来的排列有相同的奇偶性。这个结论对于任意  $n$  元排列也成立，理由如下：

设  $n$  元排列  $j_{1}j_{2}\dots j_{n}$  经过  $s$  次对换变成  $123\dots n$  。显然  $123\dots n$  是偶排列。因此如果  $j_{1}j_{2}\dots j_{n}$  是奇排列，则  $s$  必为奇数，才能把奇排列变成偶排列；如果  $j_{1}j_{2}\dots j_{n}$  是偶排列，则  $s$  必为偶数，才能保持排列的奇偶性不变。

显然，如果  $n$  元排列  $j_{1}j_{2}\dots j_{n}$  经过  $s$  次对换变成自然序排列  $123\dots n$  ，那么  $123\dots n$  经过上述  $s$  次对换(次序相反)就变成排列  $j_{1}j_{2}\dots j_{n}$  。

综上所述得：

##### 定理2
定理2 任一  $n$  元排列与排列  $123 \cdots n$  可以经过一系列对换互变, 并且所作对换的次数与这个  $n$  元排列有相同的奇偶性。

### 2.1.2 典型例题

##### 例1
例1 求6元排列413625的逆序数，并且指出它的奇偶性。

解 从左边第1个数字开始考察它与后面哪些数字构成逆序，构成逆序的数对有：

$$
4 1, 4 3, 4 2, 3 2, 6 2, 6 5.
$$

因此  $\tau(413625) = 6$  。从而 413625 是偶排列。

##### 例2
例2 求  $n$  元排列  $n(n - 1)\dots 321$  的逆序数，并且讨论它的奇偶性。

解 左边第1个数字  $n$  与后面每一个数字都构成逆序，有  $n - 1$  个逆序；左边第2个数字  $n - 1$  与后面每一个数字都构成逆序，有  $n - 2$  个逆序；依次下去，最后一对数21构成逆序，因此

$$
\begin{array}{l} \tau (n (n - 1) \dots 3 2 1) = (n - 1) + (n - 2) + \dots + 2 + 1 \\ = \frac {[ (n - 1) + 1 ] (n - 1)}{2} = \frac {n (n - 1)}{2}. \\ \end{array}
$$

当  $n = 4k$  时  $\frac{n(n - 1)}{2} = \frac{4k(4k - 1)}{2} = 2k(4k - 1)$

当  $n = 4k + 1$  时  $\frac{n(n - 1)}{2} = \frac{(4k + 1)4k}{2} = (4k + 1)2k;$

当  $n = 4k + 2$  时  $\frac{n(n - 1)}{2} = \frac{(4k + 2)(4k + 1)}{2} = (2k + 1)(4k + 1)$

当  $n = 4k + 3$  时  $\frac{n(n - 1)}{2} = \frac{(4k + 3)(4k + 2)}{2} = (4k + 3)(2k + 1)$

因此，当  $n = 4k$  或  $n = 4k + 1$  时， $n(n - 1)\cdots 321$  是偶排列；当  $n = 4k + 2$  或  $n = 4k + 3$  时， $n(n - 1)\cdots 321$  是奇排列。

##### 例3
例3 如果  $n$  元排列  $j_{1}j_{2}\dots j_{n - 1}j_{n}$  的逆序数为  $\pmb{r}$ ，求  $n$  元排列  $j_{n}j_{n - 1}\dots j_{2}j_{1}$  的逆序数。

解 在  $n$  元排列  $j_{1}j_{2}\dots j_{n - 1}j_{n}$  中构成逆序(顺序)的一对数，它们在  $j_{n}j_{n - 1}\dots j_{2}j_{1}$  中构成一对顺序(逆序)，因此  $j_{n}j_{n - 1}\dots j_{2}j_{1}$  中构成顺序的数对有  $\pmb{r}$  对，又由于排列  $j_{n}j_{n - 1}\dots j_{2}j_{1}$  中从左至右构成的数对总共有  $\mathbf{C}_n^2 = \frac{n(n - 1)}{2}$  对，因此

$$
\tau \left(j _ {n} j _ {n - 1} \dots j _ {2} j _ {1}\right) = \frac {n (n - 1)}{2} - r.
$$

##### 例4
例4 设在由  $1,2,\dots ,n$  形成的  $\pmb{n}$  元排列  $a_1a_2\dots a_kb_1b_2\dots b_{n - k}$  中，

$$
a _ {1} <   a _ {2} <   \dots <   a _ {k}, b _ {1} <   b _ {2} <   \dots <   b _ {n - k}.
$$

求排列  $a_1a_2\cdots a_kb_1b_2\cdots b_{n - k}$  的逆序数。

解 在  $a_1$  后面比  $a_1$  小的数有  $(a_1 - 1)$  个, 于是  $a_1$  跟它们构成的逆序有  $(a_1 - 1)$  对; 在  $a_2$  后面比  $a_2$  小的数有  $a_2 - 1 - 1 = a_2 - 2$  个 (注意  $a_1 < a_2$ ), 于是  $a_2$  跟它们构成的逆序有  $(a_2 - 2)$  对;  $\cdots$ ; 在  $a_k$  后面比  $a_k$  小的数有  $a_k - 1 - (k - 1) = a_k - k$  个, 于是  $a_k$  跟它们构成的逆序有  $(a_k - k)$  对, 由于  $b_1 < b_2 < \cdots < b_{n-k}$ , 因此在排列  $b_1b_2 \cdots b_{n-k}$  中没有逆序。从而

$$
\begin{array}{l} \tau \left(a _ {1} a _ {2} \dots a _ {k} b _ {1} b _ {2} \dots b _ {n - k}\right) \\ = (a _ {1} - 1) + (a _ {2} - 2) + \dots + (a _ {k} - k) \\ = \left(a _ {1} + a _ {2} + \dots + a _ {k}\right) - (1 + 2 + \dots + k) \\ = \left(\sum_ {i = 1} ^ {k} a _ {i}\right) - \frac {k (1 + k)}{2}. \\ \end{array}
$$

##### 例5
例5 设  $c_{1}c_{2}\dots c_{k}d_{1}d_{2}\dots d_{n - k}$  是由  $1,2,\dots ,n$  形成的一个  $\pmb{n}$  元排列，证明：

$$
\begin{array}{l} (- 1) ^ {\tau \left(c _ {1} c _ {2} \dots c _ {k} d _ {1} d _ {2} \dots d _ {n - k}\right)} \\ = (- 1) ^ {\tau \left(c _ {1} c _ {2} \dots c _ {k}\right) + \tau \left(d _ {1} d _ {2} \dots d _ {n - k}\right)} \cdot (- 1) ^ {c _ {1} + c _ {2} + \dots + c _ {k}} \cdot (- 1) ^ {\frac {k (k + 1)}{2}}. \\ \end{array}
$$

证明 设  $k$  元排列  $c_{1}c_{2}\dots c_{k}$  经过  $s$  次对换变成排列  $a_{1}a_{2}\dots a_{k}$ , 其中  $a_{1}<a_{2}<\cdots<a_{k}$  。由于  $\tau(a_{1}a_{2}\cdots a_{k})=0$ , 因此  $a_{1}a_{2}\cdots a_{k}$  是偶排列, 从而排列  $c_{1}c_{2}\cdots c_{k}$  与  $s$  有相同的奇偶性。在上述  $s$  次对换下,  $n$  元排列  $c_{1}c_{2}\cdots c_{k}d_{1}d_{2}\cdots d_{n-k}$  变成排列  $a_{1}a_{2}\cdots a_{k}d_{1}d_{2}\cdots d_{n-k}$  。由于对换改变排列的奇偶性, 因此

$$
\begin{array}{l} (- 1) ^ {\tau \left(c _ {1} c _ {2} \dots c _ {k} d _ {1} d _ {2} \dots d _ {n - k}\right)} \\ = (- 1) ^ {s} (- 1) ^ {\tau \left(a _ {1} a _ {2} \dots a _ {k} d _ {1} d _ {2} \dots d _ {n - k}\right)} \\ = (- 1) ^ {\tau \left(c _ {1} c _ {2} \dots c _ {k}\right)} (- 1) ^ {\left(a _ {1} - 1\right) + \left(a _ {2} - 2\right) + \dots + \left(a _ {k} - k\right) + \tau \left(d _ {1} d _ {2} \dots d _ {n - k}\right)} \\ = (- 1) ^ {\tau \left(c _ {1} c _ {2} \dots c _ {k}\right) + \tau \left(d _ {1} d _ {2} \dots d _ {n - k}\right)} (- 1) ^ {c _ {1} + c _ {2} + \dots + c _ {k}} (- 1) ^ {\frac {k (k + 1)}{2}}. \\ \end{array}
$$

##### 例6
例6 证明：在全部  $n$  元排列  $(n > 1)$  中，偶排列和奇排列各占一半。

证明 对于  $n > 1$  ，把所有  $\pmb{n}$  元偶排列组成的集合记作  $A_{n}$  ，把所有  $\pmb{n}$  元奇排列组成的集合记作  $B_{n}$  。作对换(1,2)，由于对换改变排列的奇偶性，因此它给出了  $A_{n}$  到  $B_{n}$  的一个映射  $f$  。设  $a_1a_2\dots a_n,b_1b_2\dots b_n\in A_n$  。若  $f(a_{1}a_{2}\dots a_{n}) = f(b_{1}b_{2}\dots b_{n})$  ，则

$$
f \left[ f \left(a _ {1} a _ {2} \dots a _ {n}\right) \right] = f \left[ f \left(b _ {1} b _ {2} \dots b _ {n}\right) \right].
$$

由于  $f^2$  是恒等映射，所以  $a_1 a_2 \cdots a_n = b_1 b_2 \cdots b_n$  ，因此  $f$  是单射。

任取一个  $n$  元奇排列  $d_{1}d_{2}\dots d_{n}$  ，则  $f(d_{1}d_{2}\dots d_{n})$  是偶排列，并且  $f[f(d_1d_2\dots d_n)] =$ $d_{1}d_{2}\dots d_{n}$  ，因此  $f$  是满射，从而得出  $f$  是双射。故有  $\left|A_{n}\right| = \left|B_{n}\right|$  。

### 习题2.1

##### 题1
1. 求下列各个排列的逆序数，并且指出它们的奇偶性：

(1) 315462;

(2) 365412;

(3) 654321;

(4) 7654321;

(5) 87654321;

(6) 987654321;

(7) 123456789;

(8) 518394267;

(9) 518694237。

##### 题2
2. 求下列  $n$  元排列的逆序数：

(1)  $(n - 1)(n - 2)\dots 21n;$  (2）  $23\dots (n - 1)n1.$

##### 题3
3. 写出把排列 315462 变成排列 123456 的那些对换。

##### 题4
4. 在  $1, 2, \cdots, n$  的  $n$  元排列中，

（1）位于第  $k$  个位置的数1构成多少个逆序？

（2）位于第  $k$  个位置的数  $\pmb{n}$  构成多少个逆序？

##### 题5
5. 计算下列2阶行列式：

(1)  $\left| \begin{array}{rr}3 & -1\\ 5 & 2 \end{array} \right|$

(2)  $\left| \begin{array}{ll}0 & 0\\ 1 & 4 \end{array} \right|$

(3)  $\left| \begin{array}{cc} - 2 & 5\\ 4 & -10 \end{array} \right|$ .

##### 题6
6. 利用2阶行列式，判断下述二元一次方程组是否有唯一解？如果有唯一解，求出这个解。

$$
\left\{ \begin{array}{l} 2 x _ {1} - 3 x _ {2} = 7, \\ 5 x _ {1} + 4 x _ {2} = 6. \end{array} \right.
$$

## 2.2  $n$  阶行列式的定义

### 2.2.1 内容精华

2阶行列式

$$
\left| \begin{array}{l l} a _ {1 1} & a _ {1 2} \\ a _ {2 1} & a _ {2 2} \end{array} \right| = a _ {1 1} a _ {2 2} - a _ {1 2} a _ {2 1}.
$$

2阶行列式是  $2(= 2!)$  项的代数和，其中每一项是位于不同行、不同列的两个元素的乘积，把这两个元素按照行指标成自然序排好，其列指标所成排列是偶排列时，该项带正号，奇排列时该项带负号。于是2阶行列式为

$$
\left| \begin{array}{l l} a _ {1 1} & a _ {1 2} \\ a _ {2 1} & a _ {2 2} \end{array} \right| = \sum_ {j _ {1} j _ {2}} (- 1) ^ {\tau (j _ {1} j _ {2})} a _ {1 j _ {1}} a _ {2 j _ {2}}.
$$

从2阶行列式的定义得到启发，给出  $n$  阶行列式的定义如下：

##### 定义1
定义1  $n$  阶行列式

$$
\left| \begin{array}{c c c c} a _ {1 1} & a _ {1 2} & \dots & a _ {1 n} \\ a _ {2 1} & a _ {2 2} & \dots & a _ {2 n} \\ \vdots & \vdots & & \vdots \\ a _ {n 1} & a _ {n 2} & \dots & a _ {m} \end{array} \right|
$$

是  $n!$  项的代数和, 其中每一项都是位于不同行、不同列的  $n$  个元素的乘积, 把这  $n$  个元素以行指标为自然序列排好位置, 当列指标构成的排列是偶排列时, 该项带正号; 是奇排列时, 该项带负号, 即

$$
\left| \begin{array}{c c c c} a _ {1 1} & a _ {1 2} & \dots & a _ {1 n} \\ a _ {2 1} & a _ {2 2} & \dots & a _ {2 n} \\ \vdots & \vdots & & \vdots \\ a _ {n 1} & a _ {n 2} & \dots & a _ {m} \end{array} \right| = \sum_ {j _ {1} j _ {2} \dots j _ {n}} (- 1) ^ {\tau \left(j _ {1} j _ {2} \dots j _ {n}\right)} a _ {1 j _ {1}} a _ {2 j _ {2}} \dots a _ {n j _ {n}}, \tag {1}
$$

其中  $j_{1}j_{2}\dots j_{n}$  是  $\pmb{n}$  元排列，  $\sum_{j_1j_2\dots j_n}$  表示对所有  $\pmb{n}$  元排列求和。（1)式称为  $\pmb{n}$  阶行列式的完全展开式。

令

$$
A = \left( \begin{array}{c c c c} a _ {1 1} & a _ {1 2} & \dots & a _ {1 n} \\ a _ {2 1} & a _ {2 2} & \dots & a _ {2 n} \\ \vdots & \vdots & & \vdots \\ a _ {n 1} & a _ {n 2} & \dots & a _ {m} \end{array} \right), \tag {2}
$$

则  $n$  阶行列式(1)也称为  $n$  级矩阵  $A$  的行列式，简记作  $|A|$  或者  $\det A$ 。

注意：  $n$  级矩阵  $A$  是指形如(2)的一张表，而  $n$  阶行列式  $|A|$  是指形如(1)的一个表达

式。  $n$  级矩阵的记号是圆括弧(或方括弧)，  $n$  阶行列式的记号是两条竖线。

由定义1立即得到：

- 1 阶行列式  $|a| = a$  。

- 由于3元排列123,231,312是偶排列,321,213,132是奇排列,因此3阶行列式

$$
\begin{array}{l} \left| \begin{array}{l l l} a _ {1 1} & a _ {1 2} & a _ {1 3} \\ a _ {2 1} & a _ {2 2} & a _ {2 3} \\ a _ {3 1} & a _ {3 2} & a _ {3 3} \end{array} \right| = a _ {1 1} a _ {2 2} a _ {3 3} + a _ {1 2} a _ {2 3} a _ {3 1} + a _ {1 3} a _ {2 1} a _ {3 2} - a _ {1 3} a _ {2 2} a _ {3 1} \\ - a _ {1 2} a _ {2 1} a _ {3 3} - a _ {1 1} a _ {2 3} a _ {3 2}. \tag {3} \\ \end{array}
$$

3阶行列式的6项及其所带符号可以采用下图来记忆：

![image](https://cdn-mineru.openxlab.org.cn/result/2026-03-29/ab8d15bc-2ff4-4c79-a197-bf651a1cea4f/207e4269ef225a7ac3deb00992b43d82b6f90f202725983c3c3a31a35b4fd1f0.jpg)


其中主对角线上3个元素的乘积  $a_{11}a_{22}a_{33}$ ，以及与主对角线平行的线上3个元素的乘积  $a_{12}a_{23}a_{31}, a_{13}a_{21}a_{32}$  都带正号；反对角线上3个元素的乘积  $a_{13}a_{22}a_{31}$ ，以及与反对角线平行的线上3个元素的乘积  $a_{12}a_{21}a_{33}, a_{11}a_{23}a_{32}$  都带负号。

主对角线下方的元素全为0的  $n$  阶行列式称为上三角形行列式，即

$$
\left| \begin{array}{c c c c c c c} a _ {1 1} & a _ {1 2} & a _ {1 3} & \dots & a _ {1, n - 2} & a _ {1, n - 1} & a _ {1 n} \\ 0 & a _ {2 2} & a _ {2 3} & \dots & a _ {2, n - 2} & a _ {2, n - 1} & a _ {2 n} \\ 0 & 0 & a _ {3 3} & \dots & a _ {3, n - 2} & a _ {3, n - 1} & a _ {3 n} \\ \vdots & \vdots & \vdots & & \vdots & \vdots & \vdots \\ 0 & 0 & 0 & \dots & 0 & a _ {n - 1, n - 1} & a _ {n - 1, n} \\ 0 & 0 & 0 & \dots & 0 & 0 & a _ {m} \end{array} \right| \tag {4}
$$

如何计算  $n$  阶上三角形行列式的值？

考虑  $n$  阶上三角形行列式中任意一项：

$$
(- 1) ^ {\tau \left(j _ {1} j _ {2} \dots j _ {n}\right)} a _ {1 j _ {1}} a _ {2 j _ {2}} \dots a _ {n - 2, j _ {n - 2}} a _ {n - 1, j _ {n - 1}} a _ {n j _ {n}} \tag {5}
$$

由于第  $n$  行的前  $n - 1$  个元素都为0，因此若  $j_{n} \neq n$  ，则该项等于0。于是取  $j_{n} = 0$  。对于第  $n - 1$  行，若  $j_{n - 1} \neq n - 1, n$  ，则  $a_{n - 1, j_{n - 1}} = 0$  ，从而该项等于0。于是取  $j_{n - 1} = n - 1$  或  $n$  。但是由于  $j_{n} = n$  ，因此  $j_{n - 1}$  不能取  $n$  。于是取  $j_{n - 1} = n - 1$  。依次分析，只有取  $j_{n - 2} = n - 2, \dots, j_{2} = 2, j_{1} = 1$  时， $a_{1j_{1}} a_{2j_{2}} \dots a_{n - 1, j_{n - 1}} a_{nj_{n}}$  才可能不等于0，而其他取法都会使  $a_{1j_{1}} a_{2j_{2}} \dots a_{nj_{n}} = 0$  。因此  $n$  阶上三角形行列式的值为

$$
(- 1) ^ {\tau (1 2 \dots n)} a _ {1 1} a _ {2 2} \dots a _ {n - 1, n - 1} a _ {m} = a _ {1 1} a _ {2 2} \dots a _ {n - 1, n - 1} a _ {m}.
$$

于是我们证明了下述命题：

##### 命题1
命题1  $n$  阶上三角形行列式的值等于它的主对角线上  $n$  个元素的乘积。

在  $n$  阶行列式的定义中，把每一项的  $n$  个元素的乘积按照行指标成自然序排好位置，

但是数的乘法有交换律，因此我们可以按任一次序排它们的位置，这时该项所带的符号怎么表达呢？用3阶行列式作为例子进行探索。（3)式中的第2项为  $a_{12}a_{23}a_{31}$ ，它前面带正号。我们把这3个元素相乘的次序改变成  $a_{23}a_{12}a_{31}$ ，这时如何用行指标所成排列与列指标所成排列的奇偶性来表达该项前面所带的正号呢？它的行指标所成排列213的逆序数是1，列指标所成排列321的逆序数是3， $(-1)^{1 + 3} = 1$ ，这正好表达了该项前面所带的正号。因此这一项也可以写成

$$
(- 1) ^ {\tau (2 1 3) + \tau (3 2 1)} a _ {2 3} a _ {1 2} a _ {3 1}.
$$

3阶行列式的其他各项也有类似的表达方式。由此我们猜想： $n$  阶行列式的每一项

$$
(- 1) ^ {\tau \left(j _ {1} j _ {2} \dots j _ {n}\right)} a _ {1 j _ {1}} a _ {2 j _ {2}} \dots a _ {n j _ {n}}, \tag {6}
$$

也可以写成

$$
(- 1) ^ {\tau \left(i _ {1} i _ {2} \dots i _ {n}\right) + \tau \left(k _ {1} k _ {2} \dots k _ {n}\right)} a _ {i _ {1} k _ {1}} a _ {i _ {2} k _ {2}} \dots a _ {i _ {n} k _ {n}}. \tag {7}
$$

理由如下：

设  $a_{1j_1}a_{2j_2}\dots a_{nj_n}$  经过  $\pmb{S}$  次互换两个元素的位置变成  $a_{i_1k_1}a_{i_2k_2}\dots a_{i_kk_n}$  ，则行指标排列 $12\dots n$  经过相应的  $\pmb{S}$  次对换变成  $i_1i_2\dots i_n$  ；列指标排列  $j_{1}j_{2}\dots j_{n}$  经过相应的  $\pmb{S}$  次对换变成 $k_{1}k_{2}\dots k_{n}$  。于是根据2.1节的定理2和定理1得

$$
\begin{array}{l} (- 1) ^ {\tau \left(i _ {1} i _ {2} \dots i _ {n}\right)} = (- 1) ^ {s}, \\ (- 1) ^ {\tau \left(j _ {1} j _ {2} \dots j _ {n}\right)} (- 1) ^ {s} = (- 1) ^ {\tau \left(k _ {1} k _ {2} \dots k _ {n}\right)}. \\ \end{array}
$$

从而

$$
\begin{array}{l} (- 1) ^ {\tau \left(i _ {1} i _ {2} \dots i _ {n}\right) + \tau \left(k _ {1} k _ {2} \dots k _ {n}\right)} = (- 1) ^ {s} \cdot (- 1) ^ {\tau \left(j _ {1} j _ {2} \dots j _ {n}\right)} (- 1) ^ {s} \\ = (- 1) ^ {\tau \left(j _ {1} j _ {2} \dots j _ {n}\right)} \\ \end{array}
$$

因此，项(6)与项(7)相等。

根据以上的分析得出，给定行指标的一个排列  $i_1 i_2 \cdots i_n, n$  级矩阵  $A$  的行列式  $|A|$  为

$$
| A | = \sum_ {k _ {1} k _ {2} \dots k _ {n}} (- 1) ^ {\tau \left(i _ {1} i _ {2} \dots i _ {n}\right) + \tau \left(k _ {1} k _ {2} \dots k _ {n}\right)} a _ {i _ {1} k _ {1}} a _ {i _ {2} k _ {2}} \dots a _ {i _ {n} k _ {n}}; \tag {8}
$$

或者给定列指标的一个排列  $k_{1}k_{2}\dots k_{n},n$  阶行列式  $\mid A\mid$  为

$$
| A | = \sum_ {i _ {1} i _ {2} \dots i _ {n}} (- 1) ^ {\tau \left(i _ {1} i _ {2} \dots i _ {n}\right) + \tau \left(k _ {1} k _ {2} \dots k _ {n}\right)} a _ {i _ {1} k _ {1}} a _ {i _ {2} k _ {2}} \dots a _ {i _ {n} k _ {n}}. \tag {9}
$$

特别地， $n$  阶行列式  $|A|$  的每一项可以按列指标成自然序排好位置，这时用行指标所成排列的奇偶性来决定该项前面所带的符号，即

$$
| A | = \sum_ {i _ {1} i _ {2} \dots i _ {n}} (- 1) ^ {\tau \left(i _ {1} i _ {2} \dots i _ {n}\right)} a _ {i _ {1} 1} a _ {i _ {2} 2} \dots a _ {i _ {n} n}. \tag {10}
$$

(10)式与(1)式表明，行列式中行与列的地位是对称的。

### 2.2.2 典型例题

##### 例1
例1 计算下述  $n$  阶行列式：

$$
\left| \begin{array}{c c c c c} 0 & a _ {1} & 0 & \dots & 0 \\ 0 & 0 & a _ {2} & \dots & 0 \\ \vdots & \vdots & \vdots & & \vdots \\ 0 & 0 & 0 & \dots & a _ {n - 1} \\ a _ {n} & 0 & 0 & \dots & 0 \end{array} \right|.
$$

解此行列式的每一行有  $n - 1$  个元素为0，因此在它的完全展开式中，可能不为0的项只有一项，从而这个行列式的值为

$$
(- 1) ^ {\tau (2 3 \dots n 1)} a _ {1} a _ {2} \dots a _ {n - 1} a _ {n} = (- 1) ^ {n - 1} a _ {1} a _ {2} \dots a _ {n - 1} a _ {n}.
$$

##### 例2
例2 计算下述  $n$  阶行列式：

$$
\left| \begin{array}{c c c c c} 0 & 0 & \dots & 0 & a _ {1} \\ 0 & 0 & \dots & a _ {2} & 0 \\ \vdots & \vdots & & \vdots & \vdots \\ 0 & a _ {n - 1} & \dots & 0 & 0 \\ a _ {n} & 0 & \dots & 0 & 0 \end{array} \right|.
$$

解

原式  $= (-1)^{\tau (n(n - 1)\dots 21)}a_{1}a_{2}\dots a_{n - 1}a_{n}$

$$
= (- 1) ^ {\frac {n (n - 1)}{2}} a _ {1} a _ {2} \dots a _ {n - 1} a _ {n}.
$$

点评：例2中当  $n = 4$  时，这个行列式的值为  $a_{1}a_{2}a_{3}a_{4}$  。这是反对角线上4个元素的乘积，它前面带正号。

##### 例3
例3 用行列式的定义计算

$$
\left| \begin{array}{c c c c c} a _ {1} & a _ {2} & a _ {3} & a _ {4} & a _ {5} \\ b _ {1} & b _ {2} & b _ {3} & b _ {4} & b _ {5} \\ 0 & 0 & 0 & c _ {1} & c _ {2} \\ 0 & 0 & 0 & d _ {1} & d _ {2} \\ 0 & 0 & 0 & e _ {1} & e _ {2} \end{array} \right|.
$$

解行列式的完全展开式中，每一项都包含最后三行中位于不同列的元素，而最后三行中只有第4列和第5列的元素可能不为0，因此每一项都包含0，从而这个行列式的值为0。

例4下述4阶行列式是  $x$  的几次多项式？分别求出它的  $x^4$  项和  $x^3$  项的系数：

$$
\left| \begin{array}{c c c c} 7 x & x & 1 & 2 x \\ 1 & x & 5 & - 1 \\ 4 & 3 & x & 1 \\ 2 & - 1 & 1 & x \end{array} \right|.
$$

解 4 阶行列式的完全展开式中, 每一项都是取自不同行、不同列的 4 个元素的乘积。为了得到含  $x$  的最高次幂的项, 第 4 行应当取第 4 列的元素  $x$ , 此时第 3 行取第 3 列的元素  $x$ , 第 2 行取第 2 列的元素  $x$ , 于是第 1 行只能取第 1 列的元素  $7x$  。从而这一项为

$$
(- 1) ^ {\tau (1 2 3 4)} 7 x \cdot x \cdot x \cdot x = 7 x ^ {4}.
$$

由上述取法知道，其余项都不含  $x^4$  ，因此这个行列式是  $\pmb{x}$  的4次多项式，  $x^4$  项的系数为7。

为了得到完全展开式中含  $x^3$  的项，应当在三行中取含  $x$  的元素，在其余一行中取不含  $x$  的元素。从第1行开始考虑，若取  $7x$  ，则第2行只能取  $x$  ，或5，或一1，无论取哪一个元素，都得不到含  $x^3$  的项。第1行若取第2列的元素  $x$  ，则第2行取不到含  $x$  的元素，从而应当在第3行取  $x$  ，第4行也取  $x$  ，于是第2行只能取1，这一项为

$$
(- 1) ^ {\tau (2 1 3 4)} x \cdot 1 \cdot x \cdot x = - x ^ {3}.
$$

第1行若取第3列的元素1,则第3行取不到含  $x$  的元素，从而得不到含  $x^3$  的项。第1行若取第4列的元素  $2x$  ，则第4行取不到含  $x$  的元素，从而第2行、第3行都应当取  $x$  ，于是第4行取2，则这一项为

$$
(- 1) ^ {\tau (4 2 3 1)} 2 x \cdot x \cdot x \cdot 2 = - 4 x ^ {3}.
$$

因此多项式中  $x^3$  项为

$$
- x ^ {3} - 4 x ^ {3} = - 5 x ^ {3},
$$

$x^{3}$  项的系数为  $-5$  。

##### 例5
例5 证明：如果在  $n$  阶行列式中，第  $i_1, i_2, \dots, i_k$  行分别与第  $j_1, j_2, \dots, j_l$  列交叉位置的元素都是0，并且  $k + l > n$ ，那么这个行列式的值等于0。

证明行列式的完全展开式中，每一项都包含第  $i_1,i_2,\dots ,i_k$  行中位于不同列的元素，则有  $\pmb{k}$  个元素。由已知条件，第  $i_1,i_2,\dots ,i_k$  行只有与第  $j_{1},j_{2},\dots ,j_{l}$  列以外的  $n - l$  列的交叉位置的元素可能不等于0。又由已知，  $k > n - l$  。因此每一项都含有元素0。从而这个行列式的值为0。

### 习题2.2

##### 题1
1. 按定义计算下列行列式：

(1)  $\left| \begin{array}{cccc}0 & 0 & 0 & a_{14}\\ 0 & 0 & a_{23} & a_{24}\\ 0 & a_{32} & a_{33} & a_{34}\\ a_{41} & a_{42} & a_{43} & a_{44} \end{array} \right|$

(2)  $\left| \begin{array}{ccccc}0 & \dots & 0 & a_1 & 0\\ 0 & \dots & a_2 & 0 & 0\\ \vdots & & \vdots & \vdots & \vdots \\ a_{n - 1} & \dots & 0 & 0 & 0\\ 0 & \dots & 0 & 0 & a_n \end{array} \right|$

(3)  $\left| \begin{array}{ccccc}0 & 0 & 0 & 1 & 0\\ 0 & 0 & 2 & 0 & 0\\ 0 & 3 & 8 & 0 & 0\\ 4 & 9 & 0 & 7 & 0\\ 6 & 0 & 0 & 0 & 5 \end{array} \right|$

##### 题2
2. 计算下列3阶行列式：

(1)  $\left| \begin{array}{lll}1 & 4 & 2\\ 3 & 5 & 1\\ 2 & 1 & 6 \end{array} \right|;$

(2)  $\left| \begin{array}{rrr}2 & -1 & 5\\ 3 & 1 & -2\\ 1 & 4 & 6 \end{array} \right|$

(3)  $\left| \begin{array}{ccc}a_{11} & a_{12} & a_{13}\\ 0 & a_{22} & a_{23}\\ 0 & 0 & a_{33} \end{array} \right|;$

(4)  $\left| \begin{array}{ccc}c & 0 & 0\\ 0 & a_1 & a_2\\ 0 & b_1 & b_2 \end{array} \right|$

##### 题3
3. 用行列式定义计算：

$$
\left| \begin{array}{c c c c c} a _ {1} & a _ {2} & a _ {3} & a _ {4} & a _ {5} \\ b _ {1} & b _ {2} & b _ {3} & b _ {4} & b _ {5} \\ c _ {1} & c _ {2} & 0 & 0 & 0 \\ d _ {1} & d _ {2} & 0 & 0 & 0 \\ e _ {1} & e _ {2} & 0 & 0 & 0 \end{array} \right|.
$$

##### 题4
4.  $n$  阶行列式的反对角线上  $n$  个元素的乘积一定带负号吗？

##### 题5
5. 下述行列式是  $x$  的几次多项式？分别求出  $x^4$  项和  $x^3$  项的系数。

$$
\left| \begin{array}{c c c c} 5 x & x & 1 & x \\ 1 & x & 1 & - x \\ 3 & 2 & x & 1 \\ 3 & 1 & 1 & x \end{array} \right|.
$$

##### 题6
6. 设  $n \geqslant 2$ , 证明: 如果  $n$  级矩阵  $A$  的元素为 1 或 -1, 则  $|A|$  必为偶数。

## 2.3 行列式的性质

### 2.3.1 内容精华

从行列式的定义知道， $n$  阶行列式是  $n!$  项的代数和，其中每一项是位于不同行、不同列的  $n$  个元素的乘积。当  $n$  增大时， $n!$  极其迅速地增大。例如

$$
5! = 1 2 0, \quad 1 0! = 3 6 2 8 8 0 0.
$$

如果直接用行列式的定义计算一个  $n$  阶行列式，其计算量是相当大的。因此我们必须研究行列式的性质，利用行列式的性质来简化行列式的计算，并且利用行列式的性质来研究线性方程组有唯一解的条件。

行列式有哪些性质呢？先看2阶行列式有哪些性质。

$$
\left| \begin{array}{l l} a _ {1} & a _ {2} \\ b _ {1} & b _ {2} \end{array} \right| = a _ {1} b _ {2} - a _ {2} b _ {1},
$$

$$
\left| \begin{array}{l l} a _ {1} & b _ {1} \\ a _ {2} & b _ {2} \end{array} \right| = a _ {1} b _ {2} - a _ {2} b _ {1}.
$$

由此看出，2阶行列式的行与列互换（即第1行变成第1列，第2行变成第2列，得到一个新的行列式），其行列式的值不变。 $n$  阶行列式也有此性质：

##### 性质1
性质1 行列互换，行列式的值不变。即

$$
\left| \begin{array}{c c c c} a _ {1 1} & a _ {1 2} & \dots & a _ {1 n} \\ a _ {2 1} & a _ {2 2} & \dots & a _ {2 n} \\ \vdots & \vdots & & \vdots \\ a _ {n 1} & a _ {n 2} & \dots & a _ {m n} \end{array} \right| = \left| \begin{array}{c c c c} a _ {1 1} & a _ {2 1} & \dots & a _ {n 1} \\ a _ {1 2} & a _ {2 2} & \dots & a _ {n 2} \\ \vdots & \vdots & & \vdots \\ a _ {1 n} & a _ {2 n} & \dots & a _ {m n} \end{array} \right| \tag {1}
$$

证明 把(1)式右边的行列式按照本章2.2节的公式(10)展开（注意元素的第1个下标是列指标，第2个下标是行指标）：

$$
\text {右 边} = \sum_ {i _ {1} i _ {2} \dots i _ {n}} (- 1) ^ {\tau (i _ {1} i _ {2} \dots i _ {n})} a _ {1 i _ {1}} a _ {2 i _ {2}} \dots a _ {m i _ {n}}.
$$

把(1)式左边的行列式按照定义展开（注意第1个下标是行指标）：

$$
\text {左 边} = \sum_ {i _ {1} i _ {2} \dots i _ {n}} (- 1) ^ {\tau (i _ {1} i _ {2} \dots i _ {n})} a _ {1 i _ {1}} a _ {2 i _ {2}} \dots a _ {m _ {n}}.
$$

因此(1)式成立。

性质1进一步表明了行列式的行与列的地位是对称的。因此，行列式有关行的性质，对于列也同样成立。今后我们只研究行列式有关行的性质，同学们可以把它们“翻译”成有关列的性质。

对于2阶行列式，有

$$
\left| \begin{array}{l l} a _ {1} & a _ {2} \\ k b _ {1} & k b _ {2} \end{array} \right| = a _ {1} (k b _ {2}) - a _ {2} (k b _ {1}) = k (a _ {1} b _ {2} - a _ {2} b _ {1}) = k \left| \begin{array}{l l} a _ {1} & a _ {2} \\ b _ {1} & b _ {2} \end{array} \right|.
$$

$n$  阶行列式也有此性质：

性质2行列式一行的公因子可以提出去。即

$$
\left| \begin{array}{c c c c} a _ {1 1} & a _ {1 2} & \dots & a _ {1 n} \\ \vdots & \vdots & & \vdots \\ k a _ {i 1} & k a _ {i 2} & \dots & k a _ {i n} \\ \vdots & \vdots & & \vdots \\ a _ {n 1} & a _ {n 2} & \dots & a _ {m n} \end{array} \right| = k \left| \begin{array}{c c c c} a _ {1 1} & a _ {1 2} & \dots & a _ {1 n} \\ \vdots & \vdots & & \vdots \\ a _ {i 1} & a _ {i 2} & \dots & a _ {i n} \\ \vdots & \vdots & & \vdots \\ a _ {n 1} & a _ {n 2} & \dots & a _ {m n} \end{array} \right|. \tag {2}
$$

证明 左边  $= \sum_{j_1j_2\dots j_n}(-1)^{\tau (j_1j_2\dots j_n)}a_{1j_1}\dots (ka_{ij_i})\dots a_{nj_n}$

$$
= k \sum_ {j _ {1} j _ {2} \dots j _ {n}} (- 1) ^ {\tau (j _ {1} j _ {2} \dots j _ {n})} a _ {1 j _ {1}} \dots a _ {i j _ {i}} \dots a _ {n j _ {n}}
$$

$=$  右边.

在性质2中，当  $k = 0$  时，得出：如果行列式中有一行为零（即有一行的元素全为0），那么行列式的值为0。

对于2阶行列式，有

$$
\begin{array}{l} \left| \begin{array}{c c} a _ {1} & a _ {2} \\ b _ {1} + c _ {1} & b _ {2} + c _ {2} \end{array} \right| = a _ {1} \left(b _ {2} + c _ {2}\right) - a _ {2} \left(b _ {1} + c _ {1}\right) \\ = \left(a _ {1} b _ {2} - a _ {2} b _ {1}\right) + \left(a _ {1} c _ {2} - a _ {2} c _ {1}\right) \\ = \left| \begin{array}{l l} a _ {1} & a _ {2} \\ b _ {1} & b _ {2} \end{array} \right| + \left| \begin{array}{l l} a _ {1} & a _ {2} \\ c _ {1} & c _ {2} \end{array} \right|. \\ \end{array}
$$

$n$  阶行列式也有此性质：

性质3行列式中若有某一行是两组数的和，则此行列式等于两个行列式的和，这两个行列式的这一行分别是第一组数和第二组数，而其余各行与原来行列式的相应各行相同。即

$$
\begin{array}{l} \begin{array}{c c c c} {{a _ {1 1}}} & {{a _ {1 2}}} & {{\dots}} & {{a _ {1 n}}} \\ {{\vdots}} & {{\vdots}} & {} & {{\vdots}} \\ {{b _ {1} + c _ {1}}} & {{b _ {2} + c _ {2}}} & {{\dots}} & {{b _ {n} + c _ {n}}} \\ {{\vdots}} & {{\vdots}} & {} & {{\vdots}} \\ {{a _ {n 1}}} & {{a _ {n 2}}} & {{\dots}} & {{a _ {n n}}} \end{array} \quad (\text {第} i \text {行}) \\ = \left| \begin{array}{c c c c} a _ {1 1} & a _ {1 2} & \dots & a _ {1 n} \\ \vdots & \vdots & & \vdots \\ b _ {1} & b _ {2} & \dots & b _ {n} \\ \vdots & \vdots & & \vdots \\ a _ {n 1} & a _ {n 2} & \dots & a _ {m n} \end{array} \right| + \left| \begin{array}{c c c c} a _ {1 1} & a _ {1 2} & \dots & a _ {1 n} \\ \vdots & \vdots & & \vdots \\ c _ {1} & c _ {2} & \dots & c _ {n} \\ \vdots & \vdots & & \vdots \\ a _ {n 1} & a _ {n 2} & \dots & a _ {m n} \end{array} \right|. \tag {3} \\ \end{array}
$$

证明

$$
\begin{array}{l} \text {左 边} = \sum_ {j _ {1} j _ {2} \dots j _ {n}} (- 1) ^ {\tau (j _ {1} j _ {2} \dots j _ {n})} a _ {1 j _ {1}} \dots (b _ {j _ {i}} + c _ {j _ {i}}) \dots a _ {n j _ {n}} \\ = \sum_ {j _ {1} j _ {2} \dots j _ {n}} (- 1) ^ {\tau (j _ {1} j _ {2} \dots j _ {n})} a _ {1 j _ {1}} \dots b _ {j _ {i}} \dots a _ {n j _ {n}} + \sum_ {j _ {1} j _ {2} \dots j _ {n}} (- 1) ^ {\tau (j _ {1} j _ {2} \dots j _ {n})} a _ {1 j _ {1}} \dots c _ {j _ {i}} \dots a _ {n j _ {n}} \\ = \text {右 边}. \\ \end{array}
$$

对于2阶行列式，有

$$
\left| \begin{array}{l l} a _ {1} & a _ {2} \\ b _ {1} & b _ {2} \end{array} \right| = a _ {1} b _ {2} - a _ {2} b _ {1},
$$

$$
\left| \begin{array}{l l} b _ {1} & b _ {2} \\ a _ {1} & a _ {2} \end{array} \right| = b _ {1} a _ {2} - b _ {2} a _ {1} = - (a _ {1} b _ {2} - a _ {2} b _ {1}),
$$

因此

$$
\left| \begin{array}{l l} a _ {1} & a _ {2} \\ b _ {1} & b _ {2} \end{array} \right| = - \left| \begin{array}{l l} b _ {1} & b _ {2} \\ a _ {1} & a _ {2} \end{array} \right|.
$$

$n$  阶行列式也有此性质：

##### 性质4
性质4 两行互换，行列式反号。即

$$
\begin{array}{c c c c} {{a _ {1 1}}} & {{a _ {1 2}}} & {{\dots}} & {{a _ {1 n}}} \\ {{\vdots}} & {{\vdots}} & {} & {{\vdots}} \\ {{a _ {i 1}}} & {{a _ {i 2}}} & {{\dots}} & {{a _ {i n}}} \\ {{\vdots}} & {{\vdots}} & {} & {{\vdots}} \\ {{a _ {k 1}}} & {{a _ {k 2}}} & {{\dots}} & {{a _ {k n}}} \\ {{\vdots}} & {{\vdots}} & {} & {{\vdots}} \\ {{a _ {n 1}}} & {{a _ {n 2}}} & {{\dots}} & {{a _ {n n}}} \end{array} = - \left| \begin{array}{c c c c} {{a _ {1 1}}} & {{a _ {1 2}}} & {{\dots}} & {{a _ {1 n}}} \\ {{\vdots}} & {{\vdots}} & {} & {{\vdots}} \\ {{a _ {k 1}}} & {{a _ {k 2}}} & {{\dots}} & {{a _ {k n}}} \\ {{\vdots}} & {{\vdots}} & {} & {{\vdots}} \\ {{a _ {i 1}}} & {{a _ {i 2}}} & {{\dots}} & {{a _ {i n}}} \\ {{\vdots}} & {{\vdots}} & {} & {{\vdots}} \\ {{a _ {n 1}}} & {{a _ {n 2}}} & {{\dots}} & {{a _ {n n}}} \end{array} \right| \text {第} i \text {行} \tag {4}
$$

证明 注意(4)式右边的行列式的第  $i$  行元素的第1个下标是  $k$ , 而第  $k$  行元素的第1个下标是  $i$ , 据行列式的定义, 我们有

右边  $= -\sum_{j_1\dots j_i\dots j_k\dots j_n}(-1)^{\tau (j_1\dots j_i\dots j_k\dots j_n)}a_{1j_1}\dots a_{kj_i}\dots a_{ij_k}\dots a_{nj_n}$

$$
\begin{array}{l} = - \sum_ {j _ {1} \dots j _ {k} \dots j _ {i} \dots j _ {n}} (- 1) \cdot (- 1) ^ {\tau (j _ {1} \dots j _ {k} \dots j _ {i} \dots j _ {n})} a _ {1 j _ {1}} \dots a _ {i j _ {k}} \dots a _ {k j _ {i}} \dots a _ {n j _ {n}} \\ = \sum_ {j _ {1} \dots j _ {k} \dots j _ {i} \dots j _ {n}} (- 1) ^ {\tau (j _ {1} \dots j _ {k} \dots j _ {i} \dots j _ {n})} a _ {1 j _ {1}} \dots a _ {i j _ {k}} \dots a _ {k j _ {i}} \dots a _ {n j _ {n}} \\ = \text {左 边}. \\ \end{array}
$$

##### 性质5
性质5 两行相同，行列式的值为0。即

$$
\begin{array}{r l} & {\text {第} i \text {行} \left| \begin{array}{c c c c} {a _ {1 1}} & {a _ {1 2}} & {\dots} & {a _ {1 n}} \\ {\vdots} & {\vdots} & & {\vdots} \\ {a _ {i 1}} & {a _ {i 2}} & {\dots} & {a _ {i n}} \\ {\vdots} & {\vdots} & & {\vdots} \\ {a _ {i 1}} & {a _ {i 2}} & {\dots} & {a _ {i n}} \\ {\vdots} & {\vdots} & & {\vdots} \\ {a _ {n 1}} & {a _ {n 2}} & {\dots} & {a _ {m}} \end{array} \right| = 0.} \end{array} \tag {5}
$$

证明 把(5)式左边的行列式的第  $i$  行与第  $k$  行互换，据性质4得

$$
\left| \begin{array}{c c c c} a _ {1 1} & a _ {1 2} & \dots & a _ {1 n} \\ \vdots & \vdots & & \vdots \\ a _ {i 1} & a _ {i 2} & \dots & a _ {i n} \\ \vdots & \vdots & & \vdots \\ a _ {i 1} & a _ {i 2} & \dots & a _ {i n} \\ \vdots & \vdots & & \vdots \\ a _ {n 1} & a _ {n 2} & \dots & a _ {n n} \end{array} \right| = - \left| \begin{array}{c c c c} a _ {1 1} & a _ {1 2} & \dots & a _ {1 n} \\ \vdots & \vdots & & \vdots \\ a _ {i 1} & a _ {i 2} & \dots & a _ {i n} \\ \vdots & \vdots & & \vdots \\ a _ {i 1} & a ^ {\prime} _ {i 2} & \dots & a _ {i n} \\ \vdots & \vdots & & \vdots \\ a _ {n 1} & a _ {n 2} & \dots & a _ {n n} \end{array} \right|,
$$

从而(5)式左边行列式的2倍等于0，因此(5)式左边行列式的值为0。

##### 性质6
性质6 两行成比例，行列式的值为0。即

$$
\begin{array}{r l} & {\text {第} i \text {行} \left| \begin{array}{c c c c} {a _ {1 1}} & {a _ {1 2}} & {\dots} & {a _ {1 n}} \\ {\vdots} & {\vdots} & & {\vdots} \\ {a _ {i 1}} & {a _ {i 2}} & {\dots} & {a _ {i n}} \\ {\vdots} & {\vdots} & & {\vdots} \\ {l a _ {i 1}} & {l a _ {i 2}} & {\dots} & {l a _ {i n}} \\ {\vdots} & {\vdots} & & {\vdots} \\ {a _ {n 1}} & {a _ {n 2}} & {\dots} & {a _ {n n}} \end{array} \right| = 0.} \end{array} \tag {6}
$$

证明 把(6)式左边行列式的第  $k$  行的公因子  $l$  提出去, 所得行列式有两行相同, 从而它的值为0。

##### 性质7
性质7 把一行的倍数加到另一行上，行列式的值不变。即

$$
\left| \begin{array}{c c c c} a _ {1 1} & a _ {1 2} & \dots & a _ {1 n} \\ \vdots & \vdots & & \vdots \\ a _ {i 1} & a _ {i 2} & \dots & a _ {i n} \\ \vdots & \vdots & & \vdots \\ a _ {k 1} + l a _ {i 1} & a _ {k 2} + l a _ {i 2} & \dots & a _ {k n} + l a _ {i n} \\ \vdots & \vdots & & \vdots \\ a _ {n 1} & a _ {n 2} & \dots & a _ {n n} \end{array} \right| = \left| \begin{array}{c c c c} a _ {1 1} & a _ {1 2} & \dots & a _ {1 n} \\ \vdots & \vdots & & \vdots \\ a _ {i 1} & a _ {i 2} & \dots & a _ {i n} \\ \vdots & \vdots & & \vdots \\ a _ {k 1} & a _ {k 2} & \dots & a _ {k n} \\ \vdots & \vdots & & \vdots \\ a _ {n 1} & a _ {n 2} & \dots & a _ {n n} \end{array} \right|. \tag {7}
$$

证明

$$
\begin{array}{l} \text {左 边} = \left| \begin{array}{c c c c} a _ {1 1} & a _ {1 2} & \dots & a _ {1 n} \\ \vdots & \vdots & & \vdots \\ a _ {i 1} & a _ {i 2} & \dots & a _ {i n} \\ \vdots & \vdots & & \vdots \\ a _ {k 1} & a _ {k 2} & \dots & a _ {k n} \\ \vdots & \vdots & & \vdots \\ a _ {n 1} & a _ {n 2} & \dots & a _ {n n} \end{array} \right| + \left| \begin{array}{c c c c} a _ {1 1} & a _ {1 2} & \dots & a _ {1 n} \\ \vdots & \vdots & & \vdots \\ a _ {i 1} & a _ {i 2} & \dots & a _ {i n} \\ \vdots & \vdots & & \vdots \\ l a _ {i 1} & l a _ {i 2} & \dots & l a _ {i n} \\ \vdots & \vdots & & \vdots \\ a _ {n 1} & a _ {n 2} & \dots & a _ {n n} \end{array} \right| \\ = \left| \begin{array}{c c c c} {a _ {1 1}} & {a _ {1 2}} & {\dots} & {a _ {1 n}} \\ {\vdots} & {\vdots} & & {\vdots} \\ {a _ {i 1}} & {a _ {i 2}} & {\dots} & {a _ {i n}} \\ {\vdots} & {\vdots} & & {\vdots} \\ {a _ {k 1}} & {a _ {k 2}} & {\dots} & {a _ {k n}} \\ {\vdots} & {\vdots} & & {\vdots} \\ {a _ {n 1}} & {a _ {n 2}} & {\dots} & {a _ {n n}} \end{array} \right| = \text {右 边}. \\ \end{array}
$$

行列式的定义和行列式的7条性质的内在联系，如图2-1所示。

把  $n$  级矩阵  $A$  的行与列互换得到的矩阵称为  $A$  的转置，记作  $A^{\prime}$  （或  $A^{\mathrm{T}}$  ，或  $A^{\mathrm{t}}$  ）。

由上述定义立即得出  $A^{\prime}(i;j) = A(j;i),1\leqslant i,j\leqslant n$  。

根据行列式的性质1，得

$$
\mid A ^ {\prime} \mid = \mid A \mid .
$$

根据行列式的性质7，得

如果  $A\xrightarrow{\textit{k}+\textit{i}\cdot\textit{l}}B$  ，那么  $\mid B\mid = \mid A\mid$

根据行列式的性质4，得

如果  $A \xrightarrow{(\mathfrak{i}, \mathfrak{k})} B$ ，那么  $|B| = -|A|$ 。

根据行列式的性质2，得

如果  $A \xrightarrow{\textit{i} \cdot \textit{c}} B$  ，那么  $|B| = c|A|$

其中  $c \neq 0$ 。

![image](https://cdn-mineru.openxlab.org.cn/result/2026-03-29/ab8d15bc-2ff4-4c79-a197-bf651a1cea4f/c1e16636b417950748aa4c47c1d6b875b93f30a26ff38a2e03fa0c9cfa8fd0ac.jpg)



图2-1



注：由性质2立即得出：有一行的元素全为0，则行列式的值为0。



性质2、3、4、5、6、7中把“行”换成“列”，仍然成立。


综上所述，得

如果  $A \xrightarrow{\text{初等行变换}} B$ ，那么  $|B| = l |A|$ ，其中  $l$  是某个非零数。

利用行列式的性质7, 性质4, 性质2, 可以把一个行列式化成上三角形行列式的非零数倍。这是计算行列式的基本方法之一。

利用行列式的性质3，可以把一个行列式拆成若干个行列式的和，其中每一个行列式都比较容易计算，这是计算行列式的常用方法之一。

### 2.3.2 典型例题

##### 例1
例1 计算行列式：

$$
\left| \begin{array}{c c c} - 2 & 1 & - 3 \\ 9 8 & 1 0 1 & 9 7 \\ 1 & - 3 & 4 \end{array} \right|.
$$

解

原式  $= \begin{vmatrix} -2 & 1 & -3 \\ 100 - 2 & 100 + 1 & 100 - 3 \\ 1 & -3 & 4 \end{vmatrix}$

$$
\begin{array}{l} = \left| \begin{array}{c c c} - 2 & 1 & - 3 \\ 1 0 0 & 1 0 0 & 1 0 0 \\ 1 & - 3 & 4 \end{array} \right| + \left| \begin{array}{c c c} - 2 & 1 & - 3 \\ - 2 & 1 & - 3 \\ 1 & - 3 & 4 \end{array} \right| \\ = 1 0 0 \left| \begin{array}{c c c} - 2 & 1 & - 3 \\ 1 & 1 & 1 \\ 1 & - 3 & 4 \end{array} \right| + 0 \\ = - 1 0 0 \left| \begin{array}{r r r} 1 & 1 & 1 \\ - 2 & 1 & - 3 \\ 1 & - 3 & 4 \end{array} \right| = - 1 0 0 \left| \begin{array}{r r r} 1 & 1 & 1 \\ 0 & 3 & - 1 \\ 0 & - 4 & 3 \end{array} \right| \\ \frac {② + ③ \cdot 1}{- 1 0 0} - 1 0 0 \left| \begin{array}{r r r} 1 & 1 & 1 \\ 0 & - 1 & 2 \\ 0 & - 4 & 3 \end{array} \right| = - 1 0 0 \left| \begin{array}{r r r} 1 & 1 & 1 \\ 0 & - 1 & 2 \\ 0 & 0 & - 5 \end{array} \right| \\ = - 1 0 0 \cdot 1 \cdot (- 1) \cdot (- 5) = - 5 0 0. \\ \end{array}
$$

点评：对于3阶行列式，尽量不要用完全展开式计算。应尽可能利用行列式的性质来计算。例1首先用性质3拆成两个行列式的和，其中第2个行列式利用性质5易知其值为0；第1个行列式利用性质2，性质4和性质7化成上三角形行列式，易于计算。

##### 例2
例2 计算  $n$  阶行列式：

$$
\left| \begin{array}{c c c c c} k & \lambda & \lambda & \dots & \lambda \\ \lambda & k & \lambda & \dots & \lambda \\ \vdots & \vdots & \vdots & & \vdots \\ \lambda & \lambda & \lambda & \dots & k \end{array} \right|.
$$

分析：这个  $n$  阶行列式的特点是：每一行的元素之和等于常数  $k + (n - 1)\lambda$  。因此，把第  $2,3,\dots ,n$  列都加到第1列上，就可以使第1列有公因子  $k + (n - 1)\lambda$  ，把它提出去，则第1列元素全为1。从而用行列式的性质7，容易化成上三角形行列式。以下约定：对于行列式的行进行变换的记号写在等号上面，而对于列进行变换的记号写在等号下面。

解 当  $n \geqslant 2$  时, 有

$k + (n - 1)\lambda \quad \lambda \quad \lambda \quad \dots \quad \lambda$  原式  $k + (n - 1)\lambda k\lambda \dots \lambda$  ①+② ①+③ ： ： ： ： ：… ①+④  $k + (n - 1)\lambda \quad \lambda \quad \lambda \quad \dots \quad k$

$$
= [ k + (n - 1) \lambda ] \left| \begin{array}{c c c c c} 1 & \lambda & \lambda & \dots & \lambda \\ 1 & k & \lambda & \dots & \lambda \\ \vdots & \vdots & \vdots & & \vdots \\ 1 & \lambda & \lambda & \dots & k \end{array} \right|
$$

$$
\begin{array}{l} = [ k + (n - 1) \lambda ] \left| \begin{array}{c c c c c} 1 & \lambda & \lambda & \dots & \lambda \\ 0 & k - \lambda & 0 & \dots & 0 \\ \vdots & \vdots & \vdots & & \vdots \\ 0 & 0 & 0 & \dots & k - \lambda \end{array} \right| \\ = [ k + (n - 1) \lambda ] (k - \lambda) ^ {n - 1}. \\ \end{array}
$$

当  $n = 1$  时，上述公式也成立。

点评：例2这个行列式在组合数学的对称设计中有重要应用。例2的解法不唯一，但上述解法是比较简洁和易于理解的，并且这种解法的思路可用于其他一些  $n$  阶行列式的计算中。

##### 例3
例3 证明：

$$
\left| \begin{array}{l l l} a _ {1} + c _ {1} & b _ {1} + a _ {1} & c _ {1} + b _ {1} \\ a _ {2} + c _ {2} & b _ {2} + a _ {2} & c _ {2} + b _ {2} \\ a _ {3} + c _ {3} & b _ {3} + a _ {3} & c _ {3} + b _ {3} \end{array} \right| = 2 \left| \begin{array}{l l l} a _ {1} & b _ {1} & c _ {1} \\ a _ {2} & b _ {2} & c _ {2} \\ a _ {3} & b _ {3} & c _ {3} \end{array} \right|.
$$

证明 左端行列式的每一列都是两组数的和，从而可以拆成8个行列式的和。由于两列相同，行列式的值为0；两列互换，行列式反号，因此

$$
\begin{array}{l} \left| \begin{array}{l l l} a _ {1} + c _ {1} & b _ {1} + a _ {1} & c _ {1} + b _ {1} \\ a _ {2} + c _ {2} & b _ {2} + a _ {2} & c _ {2} + b _ {2} \\ a _ {3} + c _ {3} & b _ {3} + a _ {3} & c _ {3} + b _ {3} \end{array} \right| \\ = \left| \begin{array}{l l l} a _ {1} & b _ {1} & c _ {1} \\ a _ {2} & b _ {2} & c _ {2} \\ a _ {3} & b _ {3} & c _ {3} \end{array} \right| + \left| \begin{array}{l l l} a _ {1} & b _ {1} & b _ {1} \\ a _ {2} & b _ {2} & b _ {2} \\ a _ {3} & b _ {3} & b _ {3} \end{array} \right| + \left| \begin{array}{l l l} a _ {1} & a _ {1} & c _ {1} + b _ {1} \\ a _ {2} & a _ {2} & c _ {2} + b _ {2} \\ a _ {3} & a _ {3} & c _ {3} + b _ {3} \end{array} \right| \\ + \left| \begin{array}{l l l} c _ {1} & b _ {1} & c _ {1} \\ c _ {2} & b _ {2} & c _ {2} \\ c _ {3} & b _ {3} & c _ {3} \end{array} \right| + \left| \begin{array}{l l l} c _ {1} & b _ {1} & b _ {1} \\ c _ {2} & b _ {2} & b _ {2} \\ c _ {3} & b _ {3} & b _ {3} \end{array} \right| + \left| \begin{array}{l l l} c _ {1} & a _ {1} & c _ {1} \\ c _ {2} & a _ {2} & c _ {2} \\ c _ {3} & a _ {3} & c _ {3} \end{array} \right| + \left| \begin{array}{l l l} c _ {1} & a _ {1} & b _ {1} \\ c _ {2} & a _ {2} & b _ {2} \\ c _ {3} & a _ {3} & b _ {3} \end{array} \right| \\ = \left| \begin{array}{l l l} a _ {1} & b _ {1} & c _ {1} \\ a _ {2} & b _ {2} & c _ {2} \\ a _ {3} & b _ {3} & c _ {3} \end{array} \right| + (- 1) (- 1) \left| \begin{array}{l l l} a _ {1} & b _ {1} & c _ {1} \\ a _ {2} & b _ {2} & c _ {2} \\ a _ {3} & b _ {3} & c _ {3} \end{array} \right| = 2 \left| \begin{array}{l l l} a _ {1} & b _ {1} & c _ {1} \\ a _ {2} & b _ {2} & c _ {2} \\ a _ {3} & b _ {3} & c _ {3} \end{array} \right|. \\ \end{array}
$$

##### 例4
例4 计算  $n$  阶行列式  $(n\geqslant 2)$

$$
\left| \begin{array}{c c c c c} x _ {1} - a _ {1} & x _ {2} & x _ {3} & \dots & x _ {n} \\ x _ {1} & x _ {2} - a _ {2} & x _ {3} & \dots & x _ {n} \\ x _ {1} & x _ {2} & x _ {3} - a _ {3} & \dots & x _ {n} \\ \vdots & \vdots & \vdots & & \vdots \\ x _ {1} & x _ {2} & x _ {3} & \dots & x _ {n} - a _ {n} \end{array} \right|,
$$

其中  $a_{i} \neq 0, i = 1,2,\dots,n$ 。

解先把第1行的  $(-1)$  倍分别加到第  $2,3,\dots ,n$  行上，然后各列分别提出公因子 $a_1,a_2,\dots ,a_n$  ：

原式  $= \left| \begin{array}{ccccc}x_{1} - a_{1} & x_{2} & x_{3} & \dots & x_{n}\\ a_{1} & -a_{2} & 0 & \dots & 0\\ a_{1} & 0 & -a_{3} & \dots & 0\\ \vdots & \vdots & \vdots & & \vdots \\ a_{1} & 0 & 0 & \dots & -a_{n} \end{array} \right|$

$$
\begin{array}{l} = a _ {1} a _ {2} a _ {3} \dots a _ {n} \left| \begin{array}{c c c c c} \frac {x _ {1}}{a _ {1}} - 1 & \frac {x _ {2}}{a _ {2}} & \frac {x _ {3}}{a _ {3}} & \dots & \frac {x _ {n}}{a _ {n}} \\ 1 & - 1 & 0 & \dots & 0 \\ 1 & 0 & - 1 & \dots & 0 \\ \vdots & \vdots & \vdots & & \vdots \\ 1 & 0 & 0 & \dots & - 1 \end{array} \right| \\ = a _ {1} a _ {2} a _ {3} \dots a _ {n} \left| \begin{array}{c c c c c} \sum_ {i = 1} ^ {n} \frac {x _ {i}}{a _ {i}} - 1 & \frac {x _ {2}}{a _ {2}} & \frac {x _ {3}}{a _ {3}} & \dots & \frac {x _ {n}}{a _ {n}} \\ 0 & - 1 & 0 & \dots & 0 \\ 0 & 0 & - 1 & \dots & 0 \\ \vdots & \vdots & \vdots & & \vdots \\ 0 & 0 & 0 & \dots & - 1 \end{array} \right| \\ = (- 1) ^ {n - 1} a _ {1} a _ {2} a _ {3} \dots a _ {n} \left(\sum_ {i = 1} ^ {n} \frac {x _ {i}}{a _ {i}} - 1\right). \\ \end{array}
$$

### 习题2.3

##### 题1
1. 计算下列行列式：

(1)  $\left| \begin{array}{rrr}5 & -1 & 3\\ 2 & 2 & 2\\ 196 & 203 & 199 \end{array} \right|;$

(2)  $\left| \begin{array}{ccc} - 1 & 203 & \frac{1}{3}\\ 3 & 298 & \frac{1}{2}\\ 5 & 399 & \frac{2}{3} \end{array} \right|,$

(3)  $\left| \begin{array}{rrrr}1 & 0 & -3 & 2\\ -4 & -1 & 0 & -5\\ 2 & 3 & -1 & -6\\ 3 & 3 & -4 & 1 \end{array} \right|;$

(4)  $\left| \begin{array}{cccc}1 & 2 & 3 & 4\\ 2 & 3 & 4 & 1\\ 3 & 4 & 1 & 2\\ 4 & 1 & 2 & 3 \end{array} \right|$

##### 题2
2. 计算下列  $n$  阶行列式：

(1)  $\left| \begin{array}{ccccc}a & 1 & 1 & \dots & 1\\ 1 & a & 1 & \dots & 1\\ \vdots & \vdots & \vdots & & \vdots \\ 1 & 1 & 1 & \dots & a \end{array} \right|,$

(2)  $\left| \begin{array}{cccc}a_{1} - b & a_{2} & \dots & a_{n}\\ a_{1} & a_{2} - b & \dots & a_{n}\\ \vdots & \vdots & & \vdots \\ a_{1} & a_{2} & \dots & a_{n} - b \end{array} \right|$

##### 题3
3. 证明：

$$
\begin{array}{l} \begin{array}{l l l l} & a _ {1} - b _ {1} & b _ {1} - c _ {1} & c _ {1} - a _ {1} \\ (1) & a _ {2} - b _ {2} & b _ {2} - c _ {2} & c _ {2} - a _ {2} \\ & a _ {3} - b _ {3} & b _ {3} - c _ {3} & c _ {3} - a _ {3} \end{array} = 0; \\ \left| \begin{array}{l l l} a _ {1} + b _ {1} & b _ {1} + c _ {1} & c _ {1} + a _ {1} \\ a _ {2} + b _ {2} & b _ {2} + c _ {2} & c _ {2} + a _ {2} \\ a _ {3} + b _ {3} & b _ {3} + c _ {3} & c _ {3} + a _ {3} \end{array} \right| = 2 \left| \begin{array}{l l l} a _ {1} & b _ {1} & c _ {1} \\ a _ {2} & b _ {2} & c _ {2} \\ a _ {3} & b _ {3} & c _ {3} \end{array} \right|. \tag {2} \\ \end{array}
$$

##### 题4
4. 计算下列  $n$  阶行列式：

$$
\begin{array}{l} \left| \begin{array}{c c c c c} a _ {1} & a _ {2} & a _ {3} & \dots & a _ {n} \\ b _ {2} & 1 & 0 & \dots & 0 \\ b _ {3} & 0 & 1 & \dots & 0 \\ \vdots & \vdots & \vdots & & \vdots \\ b _ {n} & 0 & 0 & \dots & 1 \end{array} \right|; \end{array} \tag {1}
$$

(2)

$$
\left| \begin{array}{c c c c} a _ {1} + b _ {1} & a _ {1} + b _ {2} & \dots & a _ {1} + b _ {n} \\ a _ {2} + b _ {1} & a _ {2} + b _ {2} & \dots & a _ {2} + b _ {n} \\ \vdots & \vdots & & \vdots \\ a _ {n} + b _ {1} & a _ {n} + b _ {2} & \dots & a _ {n} + b _ {n} \end{array} \right|.
$$

## 2.4 行列式按一行(列)展开

### 2.4.1 内容精华

$n$  阶行列式的计算能否转化成  $n - 1$  阶行列式的计算？

首先以3阶行列式为例。把3阶行列式  $|A|$  的完全展开式中6项按第1行的3个元素分成三组，每组提取公因子便得到：

$$
\begin{array}{l} | A | = \left| \begin{array}{l l l} a _ {1 1} & a _ {1 2} & a _ {1 3} \\ a _ {2 1} & a _ {2 2} & a _ {2 3} \\ a _ {3 1} & a _ {3 2} & a _ {3 3} \end{array} \right| \\ = \left(a _ {1 1} a _ {2 2} a _ {3 3} - a _ {1 1} a _ {2 3} a _ {3 2}\right) + \left(a _ {1 2} a _ {2 3} a _ {3 1} - a _ {1 2} a _ {2 1} a _ {3 3}\right) + \left(a _ {1 3} a _ {2 1} a _ {3 2} - a _ {1 3} a _ {2 2} a _ {3 1}\right) \\ = a _ {1 1} \left| \begin{array}{l l} a _ {2 2} & a _ {2 3} \\ a _ {3 2} & a _ {3 3} \end{array} \right| - a _ {1 2} \left| \begin{array}{l l} a _ {2 1} & a _ {2 3} \\ a _ {3 1} & a _ {3 3} \end{array} \right| + a _ {1 3} \left| \begin{array}{l l} a _ {2 1} & a _ {2 2} \\ a _ {3 1} & a _ {3 2} \end{array} \right|. \tag {1} \\ \end{array}
$$

这样就把3阶行列式  $|A|$  的计算转化为计算3个2阶行列式。（1)式的第1个2阶行列式

$$
\left| \begin{array}{l l} a _ {2 2} & a _ {2 3} \\ a _ {3 2} & a _ {3 3} \end{array} \right|
$$

是在3阶行列式  $|A|$  中划去  $a_{11}$  所在的第1行和第1列，剩下的元素按原来的次序组成的2阶行列式。（1)式的其他两个2阶行列式可以用类似的方法得到。由此受到启发，引出下述概念：

##### 定义1
定义1  $n$  阶行列式  $|A|$  中，划去第  $i$  行和第  $j$  列，剩下的元素按原来次序组成的  $n - 1$  阶行列式称为矩阵  $A$  的  $(i,j)$  元的余子式，记作  $M_{ij}$  。令

$$
A _ {i j} = (- 1) ^ {i + j} M _ {i j},
$$

称  $A_{ij}$  是  $A$  的  $(i,j)$  元的代数余子式。

运用代数余子式的记号，(1)式可以写成

$$
| A | = a _ {1 1} A _ {1 1} + a _ {1 2} A _ {1 2} + a _ {1 3} A _ {1 3} \tag {2}
$$

(2)式表明：3阶行列式  $|A|$  等于它的第1行元素与自己的代数余子式的乘积之和。这个结论可以推广到  $\pmb{n}$  阶行列式中，即有下述定理：

##### 定理1
定理1  $n$  阶行列式  $|A|$  等于它的第  $i$  行元素与自己的代数余子式的乘积之和，即

$$
\begin{array}{l} | A | = a _ {i 1} A _ {i 1} + a _ {i 2} A _ {i 2} + \dots + a _ {i n} A _ {i n} \\ = \sum_ {i = 1} ^ {n} a _ {i j} A _ {i j}, \tag {3} \\ \end{array}
$$

其中  $i \in \{1, 2, \dots, n\}$ , (3)式称为  $n$  阶行列式按第  $i$  行的展开式。

证明 把  $|A|$  的完全展开式的  $n!$  项按第  $i$  行的  $n$  个元素分组：

$$
\begin{array}{l} | A | = \sum_ {k _ {1} \dots k _ {i - 1} j k _ {i + 1} \dots k _ {n}} (- 1) ^ {\tau (k _ {1} \dots k _ {i - 1} j k _ {i + 1} \dots k _ {n})} a _ {1 k _ {1}} \dots a _ {i - 1, k _ {i - 1}} a _ {i j} a _ {i + 1, k _ {i + 1}} \dots a _ {n k _ {n}} \\ = \sum_ {j k _ {1} \dots k _ {i - 1} k _ {i + 1} \dots k _ {n}} (- 1) ^ {\tau (i 1 \dots (i - 1) (i + 1) \dots n) + \tau (j k _ {1} \dots k _ {i - 1} k _ {i + 1} \dots k _ {n})} a _ {i j} a _ {1 k _ {1}} \dots a _ {i - 1 k _ {i - 1}} a _ {i + 1, k _ {i + 1}} \dots a _ {n k _ {n}} \\ = \sum_ {j = 1} ^ {n} a _ {i j} (- 1) ^ {i - 1} (- 1) ^ {j - 1} \sum_ {k _ {1} \dots k _ {i - 1} k _ {i + 1} \dots k _ {n}} (- 1) ^ {\tau (k _ {1} \dots k _ {i - 1} k _ {i + 1} \dots k _ {n})} a _ {1 k _ {1}} \dots a _ {i - 1, k _ {i - 1}} a _ {i + 1, k _ {i + 1}} \dots a _ {n k _ {n}} \\ = \sum_ {j = 1} ^ {n} (- 1) ^ {i + j} a _ {i j} \left| \begin{array}{c c c c c c} a _ {1 1} & \dots & a _ {1, j - 1} & a _ {1, j + 1} & \dots & a _ {1 n} \\ \vdots & & \vdots & \vdots & & \vdots \\ a _ {i - 1, 1} & \dots & a _ {i - 1, j - 1} & a _ {i - 1, j + 1} & \dots & a _ {i - 1, n} \\ a _ {i + 1, 1} & \dots & a _ {i + 1, j - 1} & a _ {i + 1, j + 1} & \dots & a _ {i + 1, n} \\ \vdots & & \vdots & \vdots & & \vdots \\ a _ {n 1} & \dots & a _ {n, j - 1} & a _ {n, j + 1} & \dots & a _ {n n} \end{array} \right| \\ = \sum_ {j = 1} ^ {n} (- 1) ^ {i + j} a _ {i j} M _ {i j} = \sum_ {j = 1} ^ {n} a _ {i j} A _ {i j}. \\ \end{array}
$$

公式(3)称为行列式按第  $i$  行的展开式。

##### 定理2
定理2  $n$  阶行列式  $|A|$  等于它的第  $j$  列元素与自己的代数余子式的乘积之和，即

$$
\begin{array}{l} | A | = a _ {1 j} A _ {1 j} + a _ {2 j} A _ {2 j} + \dots + a _ {n j} A _ {n j} \\ = \sum_ {l = 1} ^ {n} a _ {l j} A _ {l j}. \tag {4} \\ \end{array}
$$

证明 将  $|A^{\prime}|$  按第  $j$  行展开, 由于  $A^{\prime}$  的  $(j,l)$  元等于  $A$  的  $(l,j)$  元, 并且  $A^{\prime}$  的  $(j,l)$  元的代数余子式等于  $A$  的  $(l,j)$  元的代数余子式  $A_{lj}$ , 因此

$$
| A | = \left| A ^ {\prime} \right| = a _ {1 j} A _ {1 j} + a _ {2 j} A _ {2 j} + \dots + a _ {n j} A _ {n j}.
$$

公式(4)称为行列式按第  $j$  列的展开式。

定理1和定理2把  $n$  阶行列式与  $n - 1$  阶行列式联系起来，如果能利用行列式的性质把  $n$  阶行列式的某一行(或某一列)的  $n - 1$  个元素变成0，那么  $n$  阶行列式的计算就转化为一个  $n - 1$  阶行列式的计算，从而大大减少了计算量（把计算  $n!$  项的代数和转化成计

算  $(n - 1)$  ！项的代数和)，这是计算行列式的基本方法之二。

##### 定理3
定理3  $n$  阶行列式  $|A|$  的第  $i$  行元素与第  $k$  行  $(k\neq i)$  相应元素的代数余子式的乘积之和等于0，即

$$
a _ {i 1} A _ {k 1} + a _ {i 2} A _ {k 2} + \dots + a _ {i n} A _ {k n} = 0, \text {当} k \neq i. \tag {5}
$$

证明为了使(5)式左端成为某一个矩阵的第  $k$  行元素与它自己的代数余子式的乘积之和，便于利用定理1，应构造矩阵  $B$  ，使得  $B$  的第  $k$  行元素为  $a_{i1},\dots ,a_{in}$  ，而第  $\pmb{k}$  行元素的代数余子式为  $A_{k1},A_{k2},\dots ,A_{kn}$  ，这只要使  $B$  的除第  $\pmb{k}$  行以外的其余行与  $A$  的相应行相同。于是令

$$
| B | = \left| \begin{array}{c c c c} {a _ {1 1}} & {a _ {1 2}} & {\dots} & {a _ {1 n}} \\ {\vdots} & {\vdots} & & {\vdots} \\ {a _ {i 1}} & {a _ {i 2}} & {\dots} & {a _ {i n}} \\ {\vdots} & {\vdots} & & {\vdots} \\ {a _ {i 1}} & {a _ {i 2}} & {\dots} & {a _ {i n}} \\ {\vdots} & {\vdots} & & {\vdots} \\ {a _ {n 1}} & {a _ {n 2}} & {\dots} & {a _ {m}} \end{array} \right| \quad \text {第} i \text {行},
$$

由于  $|B|$  的两行相同，因此  $|B| = 0$  。把  $|B|$  按第  $k$  行展开，得

$$
| B | = a _ {i 1} A _ {k 1} + a _ {i 2} A _ {k 2} + \dots + a _ {i n} A _ {k n}.
$$

因此

$$
a _ {i 1} A _ {k 1} + a _ {i 2} A _ {k 2} + \dots + a _ {i n} A _ {k n} = 0, (k \neq i).
$$

由于行列式的行与列的地位对称，因此也有：

##### 定理4
定理4  $n$  阶行列式  $|A|$  的第  $j$  列元素与第  $l$  列  $(l\neq j)$  的相应元素的代数余子式的乘积之和等于0，即

$$
a _ {1 j} A _ {1 l} + a _ {2 j} A _ {2 l} + \dots + a _ {n j} A _ {n l} = 0, \text {当} l \neq j. \tag {6}
$$

公式(3)，(5)与公式(4)，(6)可以分别写成

$$
\sum_ {j = 1} ^ {n} a _ {i j} A _ {k j} = \left\{ \begin{array}{l l} | A |, & \text {当} k = i, \\ 0, & \text {当} k \neq i; \end{array} \right. \tag {7}
$$

$$
\sum_ {i = 1} ^ {n} a _ {i j} A _ {i l} = \left\{ \begin{array}{l l} | A |, & \text {当} l = j, \\ 0, & \text {当} l \neq j. \end{array} \right. \tag {8}
$$

##### 例1
例1 计算行列式

$$
\left| \begin{array}{r r r} 2 & - 3 & 7 \\ - 4 & 1 & - 2 \\ 9 & - 2 & 3 \end{array} \right|.
$$

解为了尽量避免分数运算，尽可能选择1或一1所在的行(或列)，把该行(或列)的许多元素变成0，然后按这一行(或列)展开。现在选择1所在的第2行。

$$
\text {原 式} \underset {\substack {① + ② \cdot 4 \\ ③ + ② \cdot 2}} {\longrightarrow} \left| \begin{array}{ccc} - 10 & -3 & 1 \\ 0 & 1 & 0 \\ 1 & -2 & -1 \end{array} \right| = 1 \cdot (-1) ^ {2 + 2} \left| \begin{array}{cc} - 10 & 1 \\ 1 & -1 \end{array} \right| = 9.
$$

##### 例2
例2 计算行列式

$$
\left| \begin{array}{c c c} \lambda - 6 & 2 & - 2 \\ 2 & \lambda - 3 & - 4 \\ - 2 & - 4 & \lambda - 3 \end{array} \right|.
$$

解

$$
\begin{array}{l} \text {原 式} \xlongequal {\text {③} + \text {②} \cdot 1} \left| \begin{array}{c c c} \lambda - 6 & 2 & - 2 \\ 2 & \lambda - 3 & - 4 \\ 0 & \lambda - 7 & \lambda - 7 \end{array} \right| \\ \begin{array}{c c c c} \hline ② + ③ \cdot (- 1) & \lambda - 6 & 4 & - 2 \\ & 2 & \lambda + 1 & - 4 \\ & 0 & 0 & \lambda - 7 \\ \hline \end{array} \\ = (\lambda - 7) (- 1) ^ {3 + 3} \left| \begin{array}{c c} \lambda - 6 & 4 \\ 2 & \lambda + 1 \end{array} \right| \\ = (\lambda - 7) \left(\lambda^ {2} - 5 \lambda - 1 4\right) = (\lambda - 7) ^ {2} (\lambda + 2). \\ \end{array}
$$

##### 例3
例3 计算  $n$  阶行列式  $(n > 1)$

$$
\left| \begin{array}{c c c c c c c c} a & b & 0 & 0 & \dots & 0 & 0 & 0 \\ 0 & a & b & 0 & \dots & 0 & 0 & 0 \\ 0 & 0 & a & b & \dots & 0 & 0 & 0 \\ \vdots & \vdots & \vdots & \vdots & & \vdots & \vdots & \vdots \\ 0 & 0 & 0 & 0 & \dots & 0 & a & b \\ b & 0 & 0 & 0 & \dots & 0 & 0 & a \end{array} \right|.
$$

解 先按第1列展开，得

$$
\begin{array}{l} \text {原 式} = a \left| \begin{array}{c c c c c c c} a & b & 0 & \dots & 0 & 0 & 0 \\ 0 & a & b & \dots & 0 & 0 & 0 \\ \vdots & \vdots & \vdots & & \vdots & \vdots & \vdots \\ 0 & 0 & 0 & \dots & 0 & a & b \\ 0 & 0 & 0 & \dots & 0 & 0 & a \end{array} \right| \\ + b (- 1) ^ {n + 1} \left| \begin{array}{c c c c c c c} b & 0 & 0 & \dots & 0 & 0 & 0 \\ a & b & 0 & \dots & 0 & 0 & 0 \\ 0 & a & b & \dots & 0 & 0 & 0 \\ \vdots & \vdots & \vdots & & \vdots & \vdots & \vdots \\ 0 & 0 & 0 & \dots & 0 & a & b \end{array} \right| \\ = a a ^ {n - 1} + (- 1) ^ {n + 1} b b ^ {n - 1} \\ = a ^ {n} + (- 1) ^ {n + 1} b ^ {n}. \\ \end{array}
$$

$n$  阶行列式

$$
\left| \begin{array}{c c c c c} 1 & 1 & 1 & \dots & 1 \\ a _ {1} & a _ {2} & a _ {3} & \dots & a _ {n} \\ a _ {1} ^ {2} & a _ {2} ^ {2} & a _ {3} ^ {2} & \dots & a _ {n} ^ {2} \\ \vdots & \vdots & \vdots & & \vdots \\ a _ {1} ^ {n - 2} & a _ {2} ^ {n - 2} & a _ {3} ^ {n - 2} & \dots & a _ {n} ^ {n - 2} \\ a _ {1} ^ {n - 1} & a _ {2} ^ {n - 1} & a _ {3} ^ {n - 1} & \dots & a _ {n} ^ {n - 1} \end{array} \right| \tag {9}
$$

有什么特点？

它的第1行元素全是1, 第2行元素是  $n$  个数, 第3行元素是这  $n$  个数的平方,  $\cdots$ , 第  $n$  行元素是这  $n$  个数的  $(n-1)$  次方。这样的行列式称为范德蒙(Vandermonde)行列式。它的值等于什么呢?

当  $n = 2$  时，

$$
\left| \begin{array}{c c} 1 & 1 \\ a _ {1} & a _ {2} \end{array} \right| = a _ {2} - a _ {1}.
$$

当  $n = 3$  时，

$$
\begin{array}{l} \left| \begin{array}{l l l} 1 & 1 & 1 \\ a _ {1} & a _ {2} & a _ {3} \\ a _ {1} ^ {2} & a _ {2} ^ {2} & a _ {3} ^ {2} \end{array} \right| \xlongequal {\textcircled {③} + \textcircled {②} \cdot (- a _ {1})} \left| \begin{array}{l l l} 1 & 1 & 1 \\ a _ {1} & a _ {2} & a _ {3} \\ 0 & a _ {2} ^ {2} - a _ {1} a _ {2} & a _ {3} ^ {2} - a _ {1} a _ {3} \end{array} \right| \\ \underline {{\underline {{② + ①} \cdot (- a _ {1})}}} \left| \begin{array}{c c c} 1 & 1 & 1 \\ 0 & a _ {2} - a _ {1} & a _ {3} - a _ {1} \\ 0 & a _ {2} (a _ {2} - a _ {1}) & a _ {3} (a _ {3} - a _ {1}) \end{array} \right| \\ = (a _ {2} - a _ {1}) (a _ {3} - a _ {1}) \left| \begin{array}{c c} 1 & 1 \\ a _ {2} & a _ {3} \end{array} \right| \\ = \left(a _ {2} - a _ {1}\right) \left(a _ {3} - a _ {1}\right) \left(a _ {3} - a _ {2}\right). \\ \end{array}
$$

由上述受到启发，我们猜想  $n$  阶范德蒙行列式  $(n\geqslant 2)$  的值为

$$
\left| \begin{array}{c c c c c} 1 & 1 & 1 & \dots & 1 \\ a _ {1} & a _ {2} & a _ {3} & \dots & a _ {n} \\ a _ {1} ^ {2} & a _ {2} ^ {2} & a _ {3} ^ {2} & \dots & a _ {n} ^ {2} \\ \vdots & \vdots & \vdots & & \vdots \\ a _ {1} ^ {n - 2} & a _ {2} ^ {n - 2} & a _ {3} ^ {n - 2} & \dots & a _ {n} ^ {n - 2} \\ a _ {1} ^ {n - 1} & a _ {2} ^ {n - 1} & a _ {3} ^ {n - 1} & \dots & a _ {n} ^ {n - 1} \end{array} \right| = \prod_ {1 \leqslant j <   i \leqslant n} \left(a _ {i} - a _ {j}\right), \tag {10}
$$

其中  $\prod$  是连乘号，

$$
\begin{array}{l} \prod_ {1 \leqslant j <   i \leqslant n} (a _ {i} - a _ {j}) = (a _ {2} - a _ {1}) (a _ {3} - a _ {1}) \dots (a _ {n - 1} - a _ {1}) (a _ {n} - a _ {1}) \\ \cdot \left(a _ {3} - a _ {2}\right) \dots \left(a _ {n - 1} - a _ {2}\right) \left(a _ {n} - a _ {2}\right) \\ \dots \dots \dots \dots \dots \dots \dots \dots \dots \\ \cdot \left(a _ {n - 1} - a _ {n - 2}\right) \left(a _ {n} - a _ {n - 2}\right) \\ \cdot \left(a _ {n} - a _ {n - 1}\right). \\ \end{array}
$$

证明 对范德蒙行列式的阶数  $n$  作数学归纳法。

当  $n = 2$  时，上面已证明结论成立。

假设对于  $n - 1$  阶范德蒙行列式结论成立。我们来看  $n$  阶范德蒙行列式的情形。把第  $n - 1$  行的  $(-a_{1})$  倍加到第  $n$  行上，然后把第  $n - 2$  行的  $(-a_{1})$  倍加到第  $n - 1$  行上，依次类推，最后把第1行的  $(-a_{1})$  倍加到第2行上，得到

$$
\begin{array}{l} \text {原 式} = \left| \begin{array}{c c c c c} 1 & 1 & 1 & \dots & 1 \\ 0 & a _ {2} - a _ {1} & a _ {3} - a _ {1} & \dots & a _ {n} - a _ {1} \\ 0 & a _ {2} ^ {2} - a _ {1} a _ {2} & a _ {3} ^ {2} - a _ {1} a _ {3} & \dots & a _ {n} ^ {2} - a _ {1} a _ {n} \\ \vdots & \vdots & \vdots & & \vdots \\ 0 & a _ {2} ^ {n - 2} - a _ {1} a _ {2} ^ {n - 3} & a _ {3} ^ {n - 2} - a _ {1} a _ {3} ^ {n - 3} & \dots & a _ {n} ^ {n - 2} - a _ {1} a _ {n} ^ {n - 3} \\ 0 & a _ {2} ^ {n - 1} - a _ {1} a _ {2} ^ {n - 2} & a _ {3} ^ {n - 1} - a _ {1} a _ {3} ^ {n - 2} & \dots & a _ {n} ^ {n - 1} - a _ {1} a _ {n} ^ {n - 2} \end{array} \right| \\ = \left| \begin{array}{c c c c} a _ {2} - a _ {1} & a _ {3} - a _ {1} & \dots & a _ {n} - a _ {1} \\ a _ {2} (a _ {2} - a _ {1}) & a _ {3} (a _ {3} - a _ {1}) & \dots & a _ {n} (a _ {n} - a _ {1}) \\ \vdots & \vdots & & \vdots \\ a _ {2} ^ {n - 3} (a _ {2} - a _ {1}) & a _ {3} ^ {n - 3} (a _ {3} - a _ {1}) & \dots & a _ {n} ^ {n - 3} (a _ {n} - a _ {1}) \\ a _ {2} ^ {n - 2} (a _ {2} - a _ {1}) & a _ {3} ^ {n - 2} (a _ {3} - a _ {1}) & \dots & a _ {n} ^ {n - 2} (a _ {n} - a _ {1}) \end{array} \right| \\ = (a _ {2} - a _ {1}) (a _ {3} - a _ {1}) \dots (a _ {n} - a _ {1}) \left| \begin{array}{c c c c} 1 & 1 & \dots & 1 \\ a _ {2} & a _ {3} & \dots & a _ {n} \\ \vdots & \vdots & & \vdots \\ a _ {2} ^ {n - 3} & a _ {3} ^ {n - 3} & \dots & a _ {n} ^ {n - 3} \\ a _ {2} ^ {n - 2} & a _ {3} ^ {n - 2} & \dots & a _ {n} ^ {n - 2} \end{array} \right| \\ \xlongequal {\text {用 归 纳 假 设}} (a _ {2} - a _ {1}) (a _ {3} - a _ {1}) \dots (a _ {n} - a _ {1}) \prod_ {2 \leqslant j <   i \leqslant n} (a _ {i} - a _ {j}) \\ = \prod_ {2 \leqslant j <   i \leqslant n} (a _ {i} - a _ {j}). \\ \end{array}
$$

据数学归纳法原理，对一切大于1的正整数，结论都成立。

范德蒙行列式在许多实际问题中出现，我们可以用公式(10)立即写出它的值。

从(10)式看出， $n$  阶范德蒙行列式不等于 0 当且仅当  $a_1, a_2, \dots, a_n$  两两不等。

由于  $|A^{\prime}| = |A|$  ，因此也有

$$
\left| \begin{array}{c c c c c} 1 & a _ {1} & a _ {1} ^ {2} & \dots & a _ {1} ^ {n - 1} \\ 1 & a _ {2} & a _ {2} ^ {2} & \dots & a _ {2} ^ {n - 1} \\ \vdots & \vdots & \vdots & & \vdots \\ 1 & a _ {n} & a _ {n} ^ {2} & \dots & a _ {n} ^ {n - 1} \end{array} \right| = \prod_ {1 \leqslant j <   i \leqslant n} \left(a _ {i} - a _ {j}\right). \tag {11}
$$

计算行列式的方法除了前面介绍的三种：（1）化成上三角形行列式；(2)拆成若干个行列式的和；(3)把第  $2,3,\dots ,n$  列都加到第1列上(适用于各行的元素和相同)，本节再介绍下述5种方法，以后还会介绍其他方法。

（4）按一行(或一列)展开，这是基本方法之二；（5）归纳法；（6）递推关系法；（7）加边法(即升阶法)；（8）利用范德蒙行列式。

### 2.4.2 典型例题

##### 例1
例1 计算行列式：

$$
\left| \begin{array}{c c c c} - 4 & 5 & 2 & - 3 \\ 1 & - 2 & - 3 & 4 \\ 2 & 3 & 7 & 5 \\ - 3 & 6 & 4 & - 2 \end{array} \right|.
$$

解 选择元素1所在的第1列，把这一列的其余元素变成0，然后按这一列展开：

$$
\begin{array}{l} \text {原 式} = \left| \begin{array}{r r r r} 0 & - 3 & - 1 0 & 1 3 \\ 1 & - 2 & - 3 & 4 \\ 0 & 7 & 1 3 & - 3 \\ 0 & 0 & - 5 & 1 0 \end{array} \right| \\ = (- 1) ^ {2 + 1} \cdot 1 \cdot \left| \begin{array}{c c c} - 3 & - 1 0 & 1 3 \\ 7 & 1 3 & - 3 \\ 0 & - 5 & 1 0 \end{array} \right| = - \left| \begin{array}{c c c} - 3 & - 1 0 & - 7 \\ 7 & 1 3 & 2 3 \\ 0 & - 5 & 0 \end{array} \right| \\ = - (- 1) ^ {3 + 2} (- 5) \left| \begin{array}{c c} - 3 & - 7 \\ 7 & 2 3 \end{array} \right| = - 5 (- 6 9 + 4 9) = 1 0 0. \\ \end{array}
$$

##### 例2
例2 计算下述行列式，并且将结果因式分解：

$$
\left| \begin{array}{c c c c} \lambda - 1 & - 1 & - 1 & - 1 \\ - 1 & \lambda + 1 & - 1 & 1 \\ - 1 & - 1 & \lambda + 1 & 1 \\ - 1 & 1 & 1 & \lambda - 1 \end{array} \right|.
$$

解

原式  $= \left| \begin{array}{cccc}0 & (\lambda^2 -1) - 1 & -\lambda & \lambda -1 - 1\\ -1 & \lambda +1 & -1 & 1\\ 0 & -\lambda -2 & \lambda +2 & 0\\ 0 & -\lambda & 2 & \lambda -2 \end{array} \right|$

$$
\begin{array}{l} = (- 1) ^ {2 + 1} (- 1) \left| \begin{array}{c c c} \lambda^ {2} - 2 & - \lambda & \lambda - 2 \\ - \lambda - 2 & \lambda + 2 & 0 \\ - \lambda & 2 & \lambda - 2 \end{array} \right| \\ \overline {{① + ② \cdot 1}} \left| \begin{array}{c c c} \lambda^ {2} - \lambda - 2 & - \lambda & \lambda - 2 \\ 0 & \lambda + 2 & 0 \\ - \lambda + 2 & 2 & \lambda - 2 \end{array} \right| = (- 1) ^ {2 + 2} (\lambda + 2) \left| \begin{array}{c c} \lambda^ {2} - \lambda - 2 & \lambda - 2 \\ - \lambda + 2 & \lambda - 2 \end{array} \right| \\ = (\lambda + 2) (\lambda - 2) \left| \begin{array}{c c} \lambda^ {2} - \lambda - 2 & 1 \\ - \lambda + 2 & 1 \end{array} \right| = (\lambda + 2) (\lambda - 2) \left| \begin{array}{c c} \lambda^ {2} - 4 & 0 \\ - \lambda + 2 & 1 \end{array} \right| \\ = (\lambda + 2) ^ {2} (\lambda - 2) ^ {2}. \\ \end{array}
$$

##### 例3
例3 题目同2.3节典型例题的例4。

解法二 （加边法）。

$$
\begin{array}{l} \left| \begin{array}{c c c c} x _ {1} - a _ {1} & x _ {2} & \dots & x _ {n} \\ x _ {1} & x _ {2} - a _ {2} & \dots & x _ {n} \\ \vdots & \vdots & & \vdots \\ x _ {1} & x _ {2} & \dots & x _ {n} - a _ {n} \end{array} \right| = \left| \begin{array}{c c c c c} 1 & x _ {1} & x _ {2} & \dots & x _ {n} \\ 0 & x _ {1} - a _ {1} & x _ {2} & \dots & x _ {n} \\ 0 & x _ {1} & x _ {2} - a _ {2} & \dots & x _ {n} \\ \vdots & \vdots & \vdots & & \vdots \\ 0 & x _ {1} & x _ {2} & \dots & x _ {n} - a _ {n} \end{array} \right| \\ = \left| \begin{array}{c c c c c} 1 & x _ {1} & x _ {2} & \dots & x _ {n} \\ - 1 & - a _ {1} & 0 & \dots & 0 \\ - 1 & 0 & - a _ {2} & \dots & 0 \\ \vdots & \vdots & \vdots & & \vdots \\ - 1 & 0 & 0 & \dots & - a _ {n} \end{array} \right| = \left| \begin{array}{c c c c c} 1 - \sum_ {i = 1} ^ {n} \frac {x _ {i}}{a _ {i}} & x _ {1} & x _ {2} & \dots & x _ {n} \\ 0 & - a _ {1} & 0 & \dots & 0 \\ 0 & 0 & - a _ {2} & \dots & 0 \\ \vdots & \vdots & \vdots & & \vdots \\ 0 & 0 & 0 & \dots & - a _ {n} \end{array} \right| \\ = (- 1) ^ {n} a _ {1} a _ {2} \dots a _ {n} \left(1 - \sum_ {i = 1} ^ {n} \frac {x _ {i}}{a _ {i}}\right). \\ \end{array}
$$

##### 例4
例4 计算  $n$  阶行列式  $(n\geqslant 2)$

$$
D _ {n} = \left| \begin{array}{c c c c c c c c} x & 0 & 0 & \dots & 0 & 0 & a _ {0} \\ - 1 & x & 0 & \dots & 0 & 0 & a _ {1} \\ 0 & - 1 & x & \dots & 0 & 0 & a _ {2} \\ \vdots & \vdots & \vdots & & \vdots & \vdots & \vdots \\ 0 & 0 & 0 & \dots & - 1 & x & a _ {n - 2} \\ 0 & 0 & 0 & \dots & 0 & - 1 & x + a _ {n - 1} \end{array} \right|.
$$

解  $n = 2$  时，

$$
D _ {2} = \left| \begin{array}{c c} x & a _ {0} \\ - 1 & x + a _ {1} \end{array} \right| = x ^ {2} + a _ {1} x + a _ {0}.
$$

假设对于上述形式的  $n - 1$  阶行列式，有

$$
\left| \begin{array}{c c c c c c c} x & 0 & \dots & 0 & 0 & a _ {0} \\ - 1 & x & \dots & 0 & 0 & a _ {1} \\ \vdots & \vdots & & \vdots & \vdots & \vdots \\ 0 & 0 & \dots & 0 & - 1 & x + a _ {n - 2} \end{array} \right| = x ^ {n - 1} + a _ {n - 2} x ^ {n - 2} + \dots + a _ {1} x + a _ {0},
$$

现在来看上述形式的  $n$  阶行列式，把它按第1行展开，得

$$
\begin{array}{l} D _ {n} = x \left| \begin{array}{c c c c c c c} x & 0 & \dots & 0 & 0 & a _ {1} \\ - 1 & x & \dots & 0 & 0 & a _ {2} \\ \vdots & \vdots & & \vdots & \vdots & \vdots \\ 0 & 0 & \dots & - 1 & x & a _ {n - 2} \\ 0 & 0 & \dots & 0 & - 1 & x + a _ {n - 1} \end{array} \right| + (- 1) ^ {1 + n} a _ {0} \left| \begin{array}{c c c c c c} - 1 & x & 0 & \dots & 0 & 0 \\ 0 & - 1 & x & \dots & 0 & 0 \\ \vdots & \vdots & \vdots & & \vdots & \vdots \\ 0 & 0 & 0 & \dots & - 1 & x \\ 0 & 0 & 0 & \dots & 0 & - 1 \end{array} \right| \\ = x \left(x ^ {n - 1} + a _ {n - 1} x ^ {n - 2} + \dots + a _ {2} x + a _ {1}\right) + (- 1) ^ {1 + n} a _ {0} (- 1) ^ {n - 1} \\ = x ^ {n} + a _ {n - 1} x ^ {n - 1} + \dots + a _ {2} x ^ {2} + a _ {1} x + a _ {0}. \\ \end{array}
$$

根据数学归纳法原理，此命题对一切自然数  $n \geqslant 2$  都成立。

##### 例5
例5 计算  $n$  阶行列式：

$$
D _ {n} = \left| \begin{array}{c c c c c c c c c} 2 & - 1 & 0 & 0 & \dots & 0 & 0 & 0 \\ - 1 & 2 & - 1 & 0 & \dots & 0 & 0 & 0 \\ 0 & - 1 & 2 & - 1 & \dots & 0 & 0 & 0 \\ \vdots & \vdots & \vdots & \vdots & & \vdots & \vdots & \vdots \\ 0 & 0 & 0 & 0 & \dots & - 1 & 2 & - 1 \\ 0 & 0 & 0 & 0 & \dots & 0 & - 1 & 2 \end{array} \right|.
$$

解  $n = 1$  时， $D_{1} = |2| = 2$ 。下面设  $n > 1$ ，把第  $2,3,\dots,n$  列都加到第1列上，然后按第1列展开：

$$
\begin{array}{l} D _ {n} = \left| \begin{array}{c c c c c c c c c} 1 & - 1 & 0 & 0 & \dots & 0 & 0 & 0 \\ 0 & 2 & - 1 & 0 & \dots & 0 & 0 & 0 \\ 0 & - 1 & 2 & - 1 & \dots & 0 & 0 & 0 \\ \vdots & \vdots & \vdots & \vdots & & \vdots & \vdots & \vdots \\ 0 & 0 & 0 & 0 & \dots & - 1 & 2 & - 1 \\ 1 & 0 & 0 & 0 & \dots & 0 & - 1 & 2 \end{array} \right| \\ = 1 \cdot D _ {n - 1} + (- 1) ^ {n + 1} 1 \cdot (- 1) ^ {n - 1} \\ = D _ {n - 1} + 1. \\ \end{array}
$$

由此看出， $D_{1}, D_{2}, \dots, D_{n}$  是首项为 2、公差为 1 的等差数列。

因此

$$
D _ {n} = 2 + (n - 1) \cdot 1 = n + 1 。
$$

##### 例6
例6 计算  $n$  阶行列式：

$$
D _ {n} = \left| \begin{array}{c c c c c c c} a + b & a b & 0 & 0 & \dots & 0 & 0 \\ 1 & a + b & a b & 0 & \dots & 0 & 0 \\ 0 & 1 & a + b & a b & \dots & 0 & 0 \\ \vdots & \vdots & \vdots & \vdots & & \vdots & \vdots \\ 0 & 0 & 0 & 0 & \dots & 1 & a + b \end{array} \right|,
$$

其中  $a \neq b$ 。

解 若  $a = 0$  ，则  $D_{n} = b^{n}$  ；若  $b = 0$  ，则  $D_{n} = a^{n}$  。

下面设  $a \neq 0$  且  $b \neq 0$ , 当  $n \geqslant 3$  时, 按第1行展开, 得

$$
\begin{array}{l} D _ {n} = (a + b) D _ {n - 1} + (- 1) ^ {1 + 2} a b \cdot 1 \cdot D _ {n - 2} \\ = (a + b) D _ {n - 1} - a b D _ {n - 2}. \tag {12} \\ \end{array}
$$

由(12)式得

$$
D _ {n} - a D _ {n - 1} = b \left(D _ {n - 1} - a D _ {n - 2}\right). \tag {13}
$$

于是  $D_{2} - aD_{1}, D_{3} - aD_{2}, \dots, D_{n} - aD_{n-1}$  是公比为  $b$  的等比数列。从而

$$
D _ {n} - a D _ {n - 1} = \left(D _ {2} - a D _ {1}\right) b ^ {n - 2}. \tag {14}
$$

由于  $D_{1} = |a + b| = a + b$

$$
D _ {2} = \left| \begin{array}{c c} a + b & a b \\ 1 & a + b \end{array} \right| = (a + b) ^ {2} - a b = a ^ {2} + a b + b ^ {2}.
$$

因此  $D_{2} - aD_{1} = b^{2}$  。从而

$$
D _ {n} - a D _ {n - 1} = b ^ {n}. \tag {15}
$$

由(12)式又可得出

$$
D _ {n} - b D _ {n - 1} = a \left(D _ {n - 1} - b D _ {n - 2}\right). \tag {16}
$$

同理可得

$$
D _ {n} - b D _ {n - 1} = a ^ {n}. \tag {17}
$$

联立(15)、(17)式，解得

$$
D _ {n} = \frac {a ^ {n + 1} - b ^ {n + 1}}{a - b}. \tag {18}
$$

当  $n = 1,2$  时，公式(18)也成立。

##### 例7
例7 计算  $n$  阶行列式：

$$
\left| \begin{array}{c c c c c c} 1 & 2 & 3 & \dots & n - 1 & n \\ n & 1 & 2 & \dots & n - 2 & n - 1 \\ n - 1 & n & 1 & \dots & n - 3 & n - 2 \\ \vdots & \vdots & \vdots & & \vdots & \vdots \\ 2 & 3 & 4 & \dots & n & 1 \end{array} \right|.
$$

解 这个  $n$  阶行列式是把第1行的元素依次往右移1位得到的。当  $n \geqslant 3$  时，把第1行减去第2行（即把第2行的  $(-1)$  倍加到第1行上），第2行减去第3行，…，第  $n - 1$  行减去第  $n$  行，得

$$
\text {原 式} = \left| \begin{array}{c c c c c c} {1 - n} & {1} & {1} & {\dots} & {1} & {1} \\ {1} & {1 - n} & {1} & {\dots} & {1} & {1} \\ {\vdots} & {\vdots} & {\vdots} & & {\vdots} & {\vdots} \\ {1} & {1} & {1} & {\dots} & {1 - n} & {1} \\ {2} & {3} & {4} & {\dots} & {n} & {1} \end{array} \right|
$$

$$
\begin{array}{l} \begin{array}{c c c c c c c} & 0 & 1 & 1 & \dots & 1 & 1 \\ & 0 & 1 - n & 1 & \dots & 1 & 1 \\ & \vdots & \vdots & \vdots & & \vdots & \vdots \\ \overline {{① + ② \cdot 1}} & 0 & 1 & 1 & \dots & 1 - n & 1 \\ \overline {{① + ③ \cdot 1}} & \\ \dots & \\ \overline {{① + ② \cdot 1}} & \frac {n (n + 1)}{2} & 3 & 4 & \dots & n & 1 \end{array} \\ = (- 1) ^ {n + 1} \frac {n (n + 1)}{2} \left| \begin{array}{c c c c c} 1 & 1 & \dots & 1 & 1 \\ 1 - n & 1 & \dots & 1 & 1 \\ \vdots & \vdots & & \vdots & \vdots \\ 1 & 1 & \dots & 1 - n & 1 \end{array} \right| \\ = (- 1) ^ {n + 1} \frac {n (n + 1)}{2} \left| \begin{array}{c c c c c c} 1 & 1 & \dots & 1 & 1 \\ - n & 0 & \dots & 0 & 0 \\ \vdots & \vdots & & \vdots & \vdots \\ 0 & 0 & \dots & - n & 0 \end{array} \right| \\ \end{array}
$$

$$
\begin{array}{l} = (- 1) ^ {n + 1} \frac {n (n + 1)}{2} \cdot (- 1) ^ {1 + (n - 1)} 1 \cdot (- n) ^ {n - 2} \\ = (- 1) ^ {n - 1} \frac {n + 1}{2} n ^ {n - 1}. \\ \end{array}
$$

当  $n = 1,2$  时，上述结论也成立。

##### 例8
例8 设数域  $K$  上  $n$  级矩阵  $A = (a_{ij})$ , 它的  $(i,j)$  元的代数余子式记作  $A_{ij}$  。把  $A$  的每个元素都加上同一个数  $t$ , 得到的矩阵记作  $A(t) = (a_{ij} + t)$  。证明:

$$
\mid A (t) \mid = \mid A \mid + t \sum_ {i = 1} ^ {n} \sum_ {j = 1} ^ {n} A _ {i j}.
$$

证明  $|A(t)|$  的每一列都是两组数的和，利用行列式的性质3，可以把  $|A(t)|$  拆成  $2^{n}$  个行列式的和，由于两列相同，行列式的值为0，因此可能不为0的行列式至多只能有1列含元素  $t$  。于是

$$
\begin{array}{l} | A (t) | = \left| \begin{array}{c c c c} a _ {1 1} & a _ {1 2} & \dots & a _ {1 n} \\ a _ {2 1} & a _ {2 2} & \dots & a _ {2 n} \\ \vdots & \vdots & & \vdots \\ a _ {n 1} & a _ {n 2} & \dots & a _ {m} \end{array} \right| + \left| \begin{array}{c c c c} t & a _ {1 2} & \dots & a _ {1 n} \\ t & a _ {2 2} & \dots & a _ {2 n} \\ \vdots & \vdots & & \vdots \\ t & a _ {n 2} & \dots & a _ {m} \end{array} \right| \\ + \dots + \left| \begin{array}{c c c c c} a _ {1 1} & a _ {1 2} & \dots & a _ {1, n - 1} & t \\ a _ {2 1} & a _ {2 2} & \dots & a _ {2, n - 1} & t \\ \vdots & \vdots & & \vdots & \vdots \\ a _ {n 1} & a _ {n 2} & \dots & a _ {n, n - 1} & t \end{array} \right| \\ = | A | + t A _ {1 1} + t A _ {2 1} + \dots + t A _ {n 1} + \dots + t A _ {1 n} + t A _ {2 n} + \dots + t A _ {m} \\ = | A | + t \sum_ {i = 1} ^ {n} \sum_ {j = 1} ^ {n} A _ {i j}. \\ \end{array}
$$

##### 例9
例9 计算  $n$  阶行列式：

$$
D _ {n} = \left| \begin{array}{c c c c c c} 1 & 1 & 1 & \dots & 1 & 1 \\ 1 & C _ {2} ^ {1} & C _ {3} ^ {1} & \dots & C _ {n - 1} ^ {1} & C _ {n} ^ {1} \\ 1 & C _ {3} ^ {2} & C _ {4} ^ {2} & \dots & C _ {n} ^ {2} & C _ {n + 1} ^ {2} \\ \vdots & \vdots & \vdots & & \vdots & \vdots \\ 1 & C _ {n - 1} ^ {n - 2} & C _ {n} ^ {n - 2} & \dots & C _ {2 n - 4} ^ {n - 2} & C _ {2 n - 3} ^ {n - 2} \\ 1 & C _ {n} ^ {n - 1} & C _ {n + 1} ^ {n - 1} & \dots & C _ {2 n - 3} ^ {n - 1} & C _ {2 n - 2} ^ {n - 1} \end{array} \right|.
$$

解 由于  $\mathbf{C}_n^l -\mathbf{C}_{n - 1}^{l - 1} = \mathbf{C}_{n - 1}^l$  ，因此把  $D_{n}$  的第  $_n$  行减去第  $n - 1$  行，第  $n - 1$  行减去第 $n - 2$  行，…，把第2行减去第1行，得

$$
D _ {n} = \left| \begin{array}{c c c c c c} 1 & 1 & 1 & \dots & 1 & 1 \\ 0 & 1 & 2 & \dots & n - 2 & n - 1 \\ 0 & 1 & \mathrm {C} _ {3} ^ {2} & \dots & \mathrm {C} _ {n - 1} ^ {2} & \mathrm {C} _ {n} ^ {2} \\ \vdots & \vdots & \vdots & & \vdots & \vdots \\ 0 & 1 & \mathrm {C} _ {n - 1} ^ {n - 2} & \dots & \mathrm {C} _ {2 n - 5} ^ {n - 2} & \mathrm {C} _ {2 n - 4} ^ {n - 2} \\ 0 & 1 & \mathrm {C} _ {n} ^ {n - 1} & \dots & \mathrm {C} _ {2 n - 4} ^ {n - 1} & \mathrm {C} _ {2 n - 3} ^ {n - 1} \end{array} \right|
$$

$$
\begin{array}{l} = \left| \begin{array}{c c c c c} 1 & \mathrm {C} _ {2} ^ {1} & \dots & \mathrm {C} _ {n - 2} ^ {1} & \mathrm {C} _ {n - 1} ^ {1} \\ 1 & \mathrm {C} _ {3} ^ {2} & \dots & \mathrm {C} _ {n - 1} ^ {2} & \mathrm {C} _ {n} ^ {2} \\ \vdots & \vdots & & \vdots & \vdots \\ 1 & \mathrm {C} _ {n - 1} ^ {n - 2} & \dots & \mathrm {C} _ {2 n - 5} ^ {n - 2} & \mathrm {C} _ {2 n - 4} ^ {n - 2} \\ 1 & \mathrm {C} _ {n} ^ {n - 1} & \dots & \mathrm {C} _ {2 n - 4} ^ {n - 1} & \mathrm {C} _ {2 n - 3} ^ {n - 1} \end{array} \right| = \left| \begin{array}{c c c c c} 1 & \mathrm {C} _ {2} ^ {1} & \dots & \mathrm {C} _ {n - 2} ^ {1} & \mathrm {C} _ {n - 1} ^ {1} \\ 0 & \mathrm {C} _ {2} ^ {2} & \dots & \mathrm {C} _ {n - 2} ^ {2} & \mathrm {C} _ {n - 1} ^ {2} \\ \vdots & \vdots & & \vdots & \vdots \\ 0 & \mathrm {C} _ {n - 2} ^ {n - 2} & \dots & \mathrm {C} _ {2 n - 6} ^ {n - 2} & \mathrm {C} _ {2 n - 5} ^ {n - 2} \\ 0 & \mathrm {C} _ {n - 1} ^ {n - 1} & \dots & \mathrm {C} _ {2 n - 5} ^ {n - 1} & \mathrm {C} _ {2 n - 4} ^ {n - 1} \end{array} \right| \\ = \left| \begin{array}{c c c c} 1 & \dots & C _ {n - 2} ^ {2} & C _ {n - 1} ^ {2} \\ \vdots & & \vdots & \vdots \\ 1 & \dots & C _ {2 n - 6} ^ {n - 2} & C _ {2 n - 5} ^ {n - 2} \\ 1 & \dots & C _ {2 n - 5} ^ {n - 1} & C _ {2 n - 4} ^ {n - 1} \end{array} \right| = \dots \dots \\ = \left| \begin{array}{l l} 1 & \mathrm {C} _ {n - 1} ^ {n - 2} \\ 1 & \mathrm {C} _ {n} ^ {n - 1} \end{array} \right| = \left| \begin{array}{l l} 1 & n - 1 \\ 1 & n \end{array} \right| = n - (n - 1) = 1. \\ \end{array}
$$

点评：例9的解法是利用了组合数的性质之一：  $\mathbf{C}_n^l = \mathbf{C}_{n - 1}^l +\mathbf{C}_{n - 1}^{l - 1}(l <   n)$  ，以及行列式按一列展开的性质，把高阶行列式逐次降阶，并且使各列中出现的组合数  $\mathbf{C}_m^k$  中元素个数 $m$  逐渐变小，而取出的元素个数  $k$  不变，最终变成形如  $\mathbf{C}_m^m$  或  $\mathbf{C}_m^{m - 1}$  这样的组合数，易于计算。

##### 例10
例10 计算  $n$  阶列式  $(n\geqslant 2)$

$$
\left| \begin{array}{c c c c c} 1 & x _ {1} + a _ {1 1} & x _ {1} ^ {2} + a _ {2 1} x _ {1} + a _ {2 2} & \dots & x _ {1} ^ {n - 1} + a _ {n - 1, 1} x _ {1} ^ {n - 2} + \dots + a _ {n - 1, n - 1} \\ 1 & x _ {2} + a _ {1 1} & x _ {2} ^ {2} + a _ {2 1} x _ {2} + a _ {2 2} & \dots & x _ {2} ^ {n - 1} + a _ {n - 1, 1} x _ {2} ^ {n - 2} + \dots + a _ {n - 1, n - 1} \\ \vdots & \vdots & \vdots & & \vdots \\ 1 & x _ {n} + a _ {1 1} & x _ {n} ^ {2} + a _ {2 1} x _ {n} + a _ {2 2} & \dots & x _ {n} ^ {n - 1} + a _ {n - 1, 1} x _ {n} ^ {n - 2} + \dots + a _ {n - 1, n - 1} \end{array} \right|.
$$

解 此行列式的第2列是两组数  $(x_{1}, x_{2}, \cdots, x_{n})$  与  $(a_{11}, a_{11}, \cdots, a_{11})$  的和，第3列是三组数的和，…，第  $n$  列是  $n$  组数的和，从而这个行列式可以拆成  $2 \cdot 3 \cdot 4 \cdots n = n!$  个行列式的和。在这  $n!$  个行列式中，第2列为  $(a_{11}, a_{11}, \cdots, a_{11})'$  的行列式，由于第1列与第2列成比例，因此行列式的值为0；第2列为  $(x_{1}, x_{2}, \cdots, x_{n})'$  的  $\frac{1}{2} n!$  个行列式中，只要第  $j$  列不是取  $(x_{1}^{j-1}, x_{2}^{j-1}, \cdots, x_{n}^{j-1})'$  这一列，那么必有两列成比例，从而这样的行列式的值为0。因此可能不为0的行列式只有一个：

$$
\left| \begin{array}{c c c c c} 1 & x _ {1} & x _ {1} ^ {2} & \dots & x _ {1} ^ {n - 1} \\ 1 & x _ {2} & x _ {2} ^ {2} & \dots & x _ {2} ^ {n - 1} \\ \vdots & \vdots & \vdots & & \vdots \\ 1 & x _ {n} & x _ {n} ^ {2} & \dots & x _ {n} ^ {n - 1} \end{array} \right|.
$$

这是范德蒙行列式，从而原行列式的值等于

$$
\prod_ {1 \leqslant j <   i \leqslant n} (x _ {i} - x _ {j}).
$$

##### 例11
例11 计算  $n$  阶行列式  $(n \geqslant 2)$

$$
D _ {n} = \left| \begin{array}{c c c c c} 1 & 1 & \dots & 1 & 1 \\ x _ {1} & x _ {2} & \dots & x _ {n - 1} & x _ {n} \\ x _ {1} ^ {2} & x _ {2} ^ {2} & \dots & x _ {n - 1} ^ {2} & x _ {n} ^ {2} \\ \vdots & \vdots & & \vdots & \vdots \\ x _ {1} ^ {n - 2} & x _ {2} ^ {n - 2} & \dots & x _ {n - 1} ^ {n - 2} & x _ {n} ^ {n - 2} \\ x _ {1} ^ {n} & x _ {2} ^ {n} & \dots & x _ {n - 1} ^ {n} & x _ {n} ^ {n} \end{array} \right|.
$$

分析 这个行列式与范德蒙行列式的区别仅在于第  $n$  行不是  $(x_{1}^{n - 1}, x_{2}^{n - 1}, \dots, x_{n}^{n - 1})$ 。为了利用范德蒙行列式的计算公式，在原行列式的第  $n$  列右边添加一列  $(1, y, y^{2}, \dots, y^{n - 2}, y^{n - 1}, y^{n})'$ 。在第  $n - 1$  行和第  $n$  行之间插进一行  $(x_{1}^{n - 1}, x_{2}^{n - 1}, \dots, x_{n - 1}^{n - 1}, x_{n}^{n - 1}, y^{n - 1})$ 。形成一个  $n + 1$  阶行列式  $\widetilde{D}_{n + 1}$ ，它的  $(n, n + 1)$  元的余子式即为  $D_{n}$ ，也就是  $\widetilde{D}_{n + 1}$  的完全展开式中  $y^{n - 1}$  的系数乘以  $(-1)^{n + (n + 1)}$  即为  $D_{n}$ 。

解

$$
\begin{array}{l} \widetilde {D} _ {n + 1} = \left| \begin{array}{c c c c c c} 1 & 1 & \dots & 1 & 1 & 1 \\ x _ {1} & x _ {2} & \dots & x _ {n - 1} & x _ {n} & y \\ x _ {1} ^ {2} & x _ {2} ^ {2} & \dots & x _ {n - 1} ^ {2} & x _ {n} ^ {2} & y ^ {2} \\ \vdots & \vdots & & \vdots & \vdots & \vdots \\ x _ {1} ^ {n - 2} & x _ {2} ^ {n - 2} & \dots & x _ {n - 1} ^ {n - 2} & x _ {n} ^ {n - 2} & y ^ {n - 2} \\ x _ {1} ^ {n - 1} & x _ {2} ^ {n - 1} & \dots & x _ {n - 1} ^ {n - 1} & x _ {n} ^ {n - 1} & y ^ {n - 1} \\ x _ {1} ^ {n} & x _ {2} ^ {n} & \dots & x _ {n - 1} ^ {n} & x _ {n} ^ {n} & y ^ {n} \end{array} \right| \\ = (y - x _ {1}) (y - x _ {2}) \dots (y - x _ {n}) \prod_ {1 \leqslant j <   i \leqslant n} (x _ {i} - x _ {j}). \\ \end{array}
$$

$\widetilde{D}_{n+1}$  的完全展开式中  $y^{n-1}$  的系数为

$$
- \left(x _ {1} + x _ {2} + \dots + x _ {n}\right) \prod_ {1 \leqslant j <   i \leqslant n} \left(x _ {i} - x _ {j}\right)
$$

因此  $D_{n} = -(-1)^{n + (n + 1)}(x_{1} + x_{2} + \dots +x_{n})\prod_{1\leqslant j <   i\leqslant n}(x_{i} - x_{j})$

$$
= \left(x _ {1} + x _ {2} + \dots + x _ {n}\right) \prod_ {1 \leqslant j <   i \leqslant n} \left(x _ {i} - x _ {j}\right)
$$

### 习题2.4

##### 题1
1. 计算下列行列式：

(1)  $\left| \begin{array}{rrrr}1 & -2 & 0 & 4\\ 2 & -5 & 1 & -3\\ 4 & 1 & -2 & 6\\ -3 & 2 & 7 & 1 \end{array} \right|$

(3)  $\left| \begin{array}{ccc}\lambda -2 & -2 & 2\\ -2 & \lambda -5 & 4\\ 2 & 4 & \lambda -5 \end{array} \right|;$

(2)  $\left| \begin{array}{rrrr}2 & -4 & -3 & 5\\ -3 & 1 & 4 & -2\\ 7 & 2 & 5 & 3\\ 4 & -3 & -2 & 6 \end{array} \right|$

(4)  $\left| \begin{array}{ccc}\lambda -2 & -3 & -2\\ -1 & \lambda -8 & -2\\ 2 & 14 & \lambda +3 \end{array} \right|.$

##### 题2
2. 计算  $n$  阶行列式  $(n \geqslant 2)$

$$
\left| \begin{array}{c c c c c c} a _ {1} & a _ {2} & a _ {3} & \dots & a _ {n - 1} & a _ {n} \\ 1 & - 1 & 0 & \dots & 0 & 0 \\ 0 & 2 & - 2 & \dots & 0 & 0 \\ \vdots & \vdots & \vdots & & \vdots & \vdots \\ 0 & 0 & 0 & \dots & n - 1 & 1 - n \end{array} \right|.
$$

##### 题3
3. 计算  $n$  阶行列式  $(n \geqslant 2)$

$$
\left| \begin{array}{c c c c c} 1 & a _ {1} & a _ {1} ^ {2} & \dots & a _ {1} ^ {n - 1} \\ 1 & a _ {2} & a _ {2} ^ {2} & \dots & a _ {2} ^ {n - 1} \\ \vdots & \vdots & \vdots & & \vdots \\ 1 & a _ {n} & a _ {n} ^ {2} & \dots & a _ {n} ^ {n - 1} \end{array} \right|.
$$

##### 题4
4. 计算  $n$  阶行列式：

$$
D _ {n} = \left| \begin{array}{c c c c c c c c} 2 a & a ^ {2} & 0 & 0 & \dots & 0 & 0 & 0 \\ 1 & 2 a & a ^ {2} & 0 & \dots & 0 & 0 & 0 \\ 0 & 1 & 2 a & a ^ {2} & \dots & 0 & 0 & 0 \\ \vdots & \vdots & \vdots & \vdots & & \vdots & \vdots & \vdots \\ 0 & 0 & 0 & 0 & \dots & 1 & 2 a & a ^ {2} \\ 0 & 0 & 0 & 0 & \dots & 0 & 1 & 2 a \end{array} \right|.
$$

##### 题5
5. 解方程：

$$
\left| \begin{array}{c c c c} 1 & 1 & \dots & 1 \\ x & a _ {1} & \dots & a _ {n - 1} \\ x ^ {2} & a _ {1} ^ {2} & \dots & a _ {n - 1} ^ {2} \\ \vdots & \vdots & & \vdots \\ x ^ {n - 1} & a _ {1} ^ {n - 1} & \dots & a _ {n - 1} ^ {n - 1} \end{array} \right| = 0,
$$

其中  $a_1, a_2, \dots, a_{n-1}$  是两两不等的数。

##### 题6
6. 计算  $n$  阶行列式  $(n \geqslant 2)$

$$
\left| \begin{array}{c c c c c c c} 1 & 2 & 2 & \dots & 2 & 2 & 2 \\ 2 & 2 & 2 & \dots & 2 & 2 & 2 \\ 2 & 2 & 3 & \dots & 2 & 2 & 2 \\ \vdots & \vdots & \vdots & & \vdots & \vdots & \vdots \\ 2 & 2 & 2 & \dots & 2 & n - 1 & 2 \\ 2 & 2 & 2 & \dots & 2 & 2 & n \end{array} \right|.
$$

##### 题7
7. 计算  $n$  阶行列式

$$
D _ {n} = \left| \begin{array}{c c c c c c} x & y & y & \dots & y & y \\ z & x & y & \dots & y & y \\ z & z & x & \dots & y & y \\ \vdots & \vdots & \vdots & & \vdots & \vdots \\ z & z & z & \dots & x & y \\ z & z & z & \dots & z & x \end{array} \right|, y \neq z.
$$

##### 题8
8. 计算  $n$  阶行列式  $(n \geqslant 2)$

$$
\left| \begin{array}{c c c c c c} 1 & 2 & 3 & \dots & n - 1 & n \\ 2 & 3 & 4 & \dots & n & 1 \\ 3 & 4 & 5 & \dots & 1 & 2 \\ \vdots & \vdots & \vdots & & \vdots & \vdots \\ n & 1 & 2 & \dots & n - 2 & n - 1 \end{array} \right|.
$$

##### 题9
9. 用本节典型例题的例8的结果，计算下列  $n$  阶行列式：

(1)

$$
\left| \begin{array}{c c c c} 1 + x _ {1} y _ {1} & 1 + x _ {1} y _ {2} & \dots & 1 + x _ {1} y _ {n} \\ 1 + x _ {2} y _ {1} & 1 + x _ {2} y _ {2} & \dots & 1 + x _ {2} y _ {n} \\ \vdots & \vdots & & \vdots \\ 1 + x _ {n} y _ {1} & 1 + x _ {n} y _ {2} & \dots & 1 + x _ {n} y _ {n} \end{array} \right|;
$$

(2)

$$
\left| \begin{array}{c c c c c} 1 + t & t & t & \dots & t \\ t & 2 + t & t & \dots & t \\ t & t & 3 + t & \dots & t \\ \vdots & \vdots & \vdots & & \vdots \\ t & t & t & \dots & n + t \end{array} \right|.
$$

##### 题10
10. 计算  $n$  阶行列式  $(n \geqslant 2)$  :

$$
\left| \begin{array}{c c c c c} 1 & 1 & 1 & \dots & 1 \\ 1 & a _ {1} & 0 & \dots & 0 \\ 1 & 0 & a _ {2} & \dots & 0 \\ \vdots & \vdots & \vdots & & \vdots \\ 1 & 0 & 0 & \dots & a _ {n - 1} \end{array} \right|,
$$

其中  $a_1 a_2 \cdots a_{n-1} \neq 0$ 。

##### 题11
11. 计算  $n$  阶行列式：

$$
D _ {n} = \left| \begin{array}{c c c c c c c} 5 & 3 & 0 & 0 & \dots & 0 & 0 \\ 2 & 5 & 3 & 0 & \dots & 0 & 0 \\ 0 & 2 & 5 & 3 & \dots & 0 & 0 \\ \vdots & \vdots & \vdots & \vdots & & \vdots & \vdots \\ 0 & 0 & 0 & 0 & \dots & 2 & 5 \end{array} \right|.
$$

##### 题12
12. 计算  $n$  阶行列式：

$$
D _ {n} = \left| \begin{array}{c c c c c c c} 1 + x ^ {2} & x & 0 & 0 & \dots & 0 & 0 \\ x & 1 + x ^ {2} & x & 0 & \dots & 0 & 0 \\ 0 & x & 1 + x ^ {2} & x & \dots & 0 & 0 \\ \vdots & \vdots & \vdots & \vdots & & \vdots & \vdots \\ 0 & 0 & 0 & 0 & \dots & x & 1 + x ^ {2} \end{array} \right|.
$$

##### 题13
13. 计算  $n$  阶行列式  $(n \geqslant 2)$

$$
\left| \begin{array}{c c c c} 1 & 1 & \dots & 1 \\ x _ {1} + 1 & x _ {2} + 1 & \dots & x _ {n} + 1 \\ x _ {1} ^ {2} + x _ {1} & x _ {2} ^ {2} + x _ {2} & \dots & x _ {n} ^ {2} + x _ {n} \\ x _ {1} ^ {3} + x _ {1} ^ {2} & x _ {2} ^ {3} + x _ {2} ^ {2} & \dots & x _ {n} ^ {3} + x _ {n} ^ {2} \\ \vdots & \vdots & & \vdots \\ x _ {1} ^ {n - 1} + x _ {1} ^ {n - 2} & x _ {2} ^ {n - 1} + x _ {2} ^ {n - 2} & \dots & x _ {n} ^ {n - 1} + x _ {n} ^ {n - 2} \end{array} \right|.
$$

##### 题14
14. 计算  $n$  阶行列式：

$$
\left| \begin{array}{c c c c c c c} 1 - a _ {1} & a _ {2} & 0 & 0 & \dots & 0 & 0 \\ - 1 & 1 - a _ {2} & a _ {3} & 0 & \dots & 0 & 0 \\ 0 & - 1 & 1 - a _ {3} & a _ {4} & \dots & 0 & 0 \\ \vdots & \vdots & \vdots & \vdots & & \vdots & \vdots \\ 0 & 0 & 0 & 0 & \dots & - 1 & 1 - a _ {n} \end{array} \right|.
$$

## 2.5 克莱姆(Cramer)法则

### 2.5.1 内容精华

现在来回答本章开头提出的问题：对于数域  $K$  上  $\pmb{n}$  个方程的  $\pmb{n}$  元线性方程组，能不能直接从方程组的系数和常数项判断它有没有解？有多少解？

$$
\left\{ \begin{array}{l} a _ {1 1} x _ {1} + a _ {1 2} x _ {2} + \dots + a _ {1 n} x _ {n} = b _ {1}, \\ a _ {2 1} x _ {1} + a _ {2 2} x _ {2} + \dots + a _ {2 n} x _ {n} = b _ {2}, \\ \dots \quad \dots \quad \dots \quad \dots \quad \dots \\ a _ {n 1} x _ {1} + a _ {n 2} x _ {2} + \dots + a _ {m} x _ {n} = b _ {n}. \end{array} \right. \tag {1}
$$

方程组(1)的系数矩阵记作  $A$  ，增广矩阵记作  $\widetilde{A}$  .对增广矩阵  $\widetilde{A}$  施行初等行变换化成阶梯形矩阵  $\widetilde{J}$  ，此时系数矩阵  $A$  被化成阶梯形矩阵  $J$  ，其中  $J$  比  $\widetilde{J}$  少最后一列。

根据第1章1.2节的定理1，如果相应的阶梯形方程组出现“ $0 = d$ （其中  $d \neq 0$ ）”这种方程，那么原方程组无解。此时  $J$  必有零行（ $\tilde{J}$  的这一行  $(0, \dots, 0, d)$  对于  $J$  来讲是  $(0, \dots, 0)$ ），从而  $|J| = 0$ 。

如果相应的阶梯形方程组不出现“ $0 = d$ （其中  $d \neq 0$ ）”这种方程，那么原方程组有解。此时当  $\widetilde{J}$  的非零行数目小于未知量数目  $n$  时，原方程组有无穷多个解。这种情形  $\widetilde{J}$  有零

行，从而  $J$  也有零行，于是  $|J| = 0$  。

如果相应的阶梯形方程组不出现“ $0 = d$ （其中  $d \neq 0$ ）”这种方程，并且  $\widetilde{J}$  的非零行数目等于未知量数目  $n$ ，那么原方程组有唯一解。这种情形  $J$  的非零行数目也等于  $n$ （否则，相应的阶梯形方程组会出现“ $0 = d$ （其中  $d \neq 0$ ）”这种方程）。于是  $J$  有  $n$  个主元，它们位于不同列，因此  $J$  必定形如

$$
J = \left( \begin{array}{c c c c} c _ {1 1} & c _ {1 2} & \dots & c _ {1 n} \\ 0 & c _ {2 2} & \dots & c _ {2 n} \\ \vdots & \vdots & & \vdots \\ 0 & 0 & \dots & c _ {m n} \end{array} \right),
$$

其中  $c_{11}, c_{22}, \dots, c_{mn}$  全不为 0。从而

$$
| J | = c _ {1 1} c _ {2 2} \dots c _ {m n} \neq 0.
$$

上述表明：原线性方程组无解或有无穷多个解时，  $|J| = 0$  ；有唯一解时，  $|J|\neq 0$  。由此得出：

原线性方程组有唯一解当且仅当  $|J| \neq 0$ 。

根据行列式的性质2、4、7，得出

$$
| J | = l | A |,
$$

其中  $l$  是某个非零数。因此  $|J| \neq 0$  当且仅当  $|A| \neq 0$  。结合上述结论，便得出：

##### 定理1
定理1 数域  $K$  上  $n$  个方程的  $n$  元线性方程组有唯一解的充分必要条件是它的系数行列式（即系数矩阵  $A$  的行列式  $|A|$ ）不等于0。

从定理1的证明过程看到，关键是利用行列式的性质2、性质4、性质7，得出

如果

那么  $|J| = l|A|$ ，其中  $l$  是某个非零数。

即， $n$  级矩阵的初等行变换不改变它们的行列式的非零性质。

把定理1应用到齐次线性方程组上便得到下述结论：

##### 推论1
推论1 数域  $K$  上  $n$  个方程的  $n$  元齐次线性方程组只有零解的充分必要条件是它的系数行列式不等于0。从而它有非零解的充分必要条件是它的系数行列式等于0。

现在来回答  $n$  个方程的  $n$  元线性方程组有唯一解时，这个解能不能用原方程组的系数和常数项表达？

两个方程的二元一次方程组有唯一解时，它的解为  $\left(\frac{|B_1|}{|A|},\frac{|B_2|}{|A|}\right)$ ，其中  $B_{1}, B_{2}$  分别是把系数矩阵  $A$  的第 1、2 列换成常数项得到的矩阵。由此受到启发，把  $n$  个方程的  $n$  元线性方程组(1)的系数矩阵  $A$  的第  $j$  列换成常数项，得到的矩阵记作  $B_{j}, j = 1,2,\dots,n$ ，即

$$
B _ {j} = \left( \begin{array}{c c c c c c c} a _ {1 1} & \dots & a _ {1, j - 1} & b _ {1} & a _ {1, j + 1} & \dots & a _ {1 n} \\ a _ {2 1} & \dots & a _ {2, j - 1} & b _ {2} & a _ {2, j + 1} & \dots & a _ {2 n} \\ \vdots & & \vdots & \vdots & \vdots & & \vdots \\ a _ {n 1} & \dots & a _ {n, j - 1} & b _ {n} & a _ {n, j + 1} & \dots & a _ {m n} \end{array} \right).
$$

##### 定理2
定理2  $n$  个方程的  $n$  元线性方程组(1)的系数行列式  $|A| \neq 0$  时，它的唯一解是

$$
\left(\frac {\left| B _ {1} \right|}{\left| A \right|}, \frac {\left| B _ {2} \right|}{\left| A \right|}, \dots , \frac {\left| B _ {n} \right|}{\left| A \right|}\right). \tag {2}
$$

证明 把  $x_{j} = \frac{|B_{j}|}{|A|} (j = 1,2,\dots ,n)$  代入第  $_i$  个方程的左端，得

$$
\begin{array}{l} a _ {i 1} \frac {\left| B _ {1} \right|}{\left| A \right|} + a _ {i 2} \frac {\left| B _ {2} \right|}{\left| A \right|} + \dots + a _ {i n} \frac {\left| B _ {n} \right|}{\left| A \right|} \\ = \sum_ {j = 1} ^ {n} a _ {i j} \frac {\left| B _ {j} \right|}{\left| A \right|} = \frac {1}{\left| A \right|} \sum_ {j = 1} ^ {n} a _ {i j} \left| B _ {j} \right| \\ = \frac {1}{| A |} \sum_ {j = 1} ^ {n} a _ {i j} \left(\sum_ {k = 1} ^ {n} b _ {k} A _ {k j}\right) \\ = \frac {1}{| A |} \sum_ {j = 1} ^ {n} \sum_ {k = 1} ^ {n} a _ {i j} b _ {k} A _ {k j} \\ = \frac {1}{| A |} \sum_ {k = 1} ^ {n} \sum_ {j = 1} ^ {n} a _ {i j} b _ {k} A _ {k j} = \frac {1}{| A |} \sum_ {k = 1} ^ {n} b _ {k} \left(\sum_ {j = 1} ^ {n} a _ {i j} A _ {k j}\right) \\ = \frac {1}{| A |} b _ {i} | A | = b _ {i}. \\ \end{array}
$$

因此有序数组(2)是线性方程组(1)的一个解。

从定理2的证明过程看到，关键是利用行列式按一行(列)展开定理： $n$  阶行列式  $|A|$  的第  $i$  行元素与第  $k$  行相应元素的代数余子式的乘积之和，当  $i = k$  时，为  $|A|$ ；当  $i \neq k$  时，为0。 $n$  阶行列式的第  $j$  列元素与自己的代数余子式的乘积之和等于这个行列式的值。

在定理2的证明过程的第3步，把  $|B_j|$  按第  $j$  列展开，注意  $|B_j|$  的  $(k,j)$  元的代数余子式与  $|A|$  的  $(k,j)$  元的代数余子式  $A_{kj}$  一致。第4步利用了双重连加号可交换次序。

由此可知，利用行列式的性质2、性质4、性质7和行列式按一行(列)展开定理，可圆满地解决  $n$  个方程的  $n$  元线性方程组直接从系数和常数项判断它是否有唯一解，以及这个解的公式表示问题。定理1和定理2合起来称为克莱姆(Cramer)法则。

### 2.5.2 典型例题

##### 例1
例1 判断下述数域  $K$  上  $n$  元线性方程组有无解？有多少解？

$$
\left\{ \begin{array}{l} x _ {1} + a x _ {2} + a ^ {2} x _ {3} + \dots + a ^ {n - 1} x _ {n} = b _ {1}, \\ x _ {1} + a ^ {2} x _ {2} + a ^ {4} x _ {3} + \dots + a ^ {2 (n - 1)} x _ {n} = b _ {2}, \\ \dots \quad \dots \quad \dots \quad \dots \quad \dots \quad \dots \\ x _ {1} + a ^ {n} x _ {2} + a ^ {2 n} x _ {3} + \dots + a ^ {n (n - 1)} x _ {n} = b _ {n}, \end{array} \right.
$$

其中  $a \neq 0$  并且当  $0 < r < n$  时， $a^r \neq 1$ 。

解 由于  $a \neq 0$  且当  $0 < r < n$  时,  $a^r \neq 1$ , 因此  $a, a^2, \dots, a^n$  是两两不等的非零数。上述方程组的系数行列式为

$$
\left| \begin{array}{c c c c c} 1 & a & a ^ {2} & \dots & a ^ {n - 1} \\ 1 & a ^ {2} & a ^ {4} & \dots & a ^ {2 (n - 1)} \\ \vdots & \vdots & \vdots & & \vdots \\ 1 & a ^ {n} & a ^ {2 n} & \dots & a ^ {n (n - 1)} \end{array} \right| = \left| \begin{array}{c c c c} 1 & 1 & \dots & 1 \\ a & a ^ {2} & \dots & a ^ {n} \\ a ^ {2} & a ^ {4} & \dots & a ^ {2 n} \\ \vdots & \vdots & & \vdots \\ a ^ {n - 1} & a ^ {2 (n - 1)} & \dots & a ^ {n (n - 1)} \end{array} \right|.
$$

上式右端是范德蒙行列式，由于  $a, a^2, \dots, a^n$  两两不等，因此这个范德蒙行列式的值不等于0。从而上述线性方程组有唯一解。

##### 例2
例2 当  $\lambda$  取什么值时，下述齐次线性方程组有非零解？

$$
\left\{ \begin{array}{c c c} (\lambda - 3) x _ {1} & - x _ {2} & + x _ {4} = 0, \\ - x _ {1} + (\lambda - 3) x _ {2} & + x _ {3} & = 0, \\ x _ {2} + (\lambda - 3) x _ {3} & - x _ {4} = 0, \\ x _ {1} & - x _ {3} + (\lambda - 3) x _ {4} = 0. \end{array} \right.
$$

解 此方程组的系数行列式为

$$
\begin{array}{l} \left| \begin{array}{r r r r} \lambda - 3 & - 1 & 0 & 1 \\ - 1 & \lambda - 3 & 1 & 0 \\ 0 & 1 & \lambda - 3 & - 1 \\ 1 & 0 & - 1 & \lambda - 3 \end{array} \right| = \left| \begin{array}{r r r r} \lambda - 3 & - 1 & 0 & 1 \\ \lambda - 3 & \lambda - 3 & 1 & 0 \\ \lambda - 3 & 1 & \lambda - 3 & - 1 \\ \lambda - 3 & 0 & - 1 & \lambda - 3 \end{array} \right| \\ = (\lambda - 3) \left| \begin{array}{c c c c} 1 & - 1 & 0 & 1 \\ 1 & \lambda - 3 & 1 & 0 \\ 1 & 1 & \lambda - 3 & - 1 \\ 1 & 0 & - 1 & \lambda - 3 \end{array} \right| = (\lambda - 3) \left| \begin{array}{c c c c} 1 & - 1 & 0 & 1 \\ 0 & \lambda - 2 & 1 & - 1 \\ 0 & 2 & \lambda - 3 & - 2 \\ 0 & 1 & - 1 & \lambda - 4 \end{array} \right| \\ = (\lambda - 3) \left| \begin{array}{c c c} \lambda - 2 & 1 & - 1 \\ 2 & \lambda - 3 & - 2 \\ 1 & - 1 & \lambda - 4 \end{array} \right| = (\lambda - 3) \left| \begin{array}{c c c} \lambda - 2 & 1 & 0 \\ 2 & \lambda - 3 & \lambda - 5 \\ 1 & - 1 & \lambda - 5 \end{array} \right| \\ = (\lambda - 3) (\lambda - 5) \left| \begin{array}{c c c} \lambda - 2 & 1 & 0 \\ 2 & \lambda - 3 & 1 \\ 1 & - 1 & 1 \end{array} \right| = (\lambda - 3) (\lambda - 5) \left| \begin{array}{c c c} \lambda - 2 & 1 & 0 \\ 1 & \lambda - 2 & 0 \\ 1 & - 1 & 1 \end{array} \right| \\ = (\lambda - 3) (\lambda - 5) \left| \begin{array}{c c} \lambda - 2 & 1 \\ 1 & \lambda - 2 \end{array} \right| = (\lambda - 3) (\lambda - 5) [ (\lambda - 2) ^ {2} - 1 ] \\ = (\lambda - 1) (\lambda - 3) ^ {2} (\lambda - 5). \\ \end{array}
$$

从而上述齐次线性方程组有非零解

$$
\begin{array}{l} \Longleftrightarrow (\lambda - 1) (\lambda - 3) ^ {2} (\lambda - 5) = 0 \\ \Longleftrightarrow \lambda = 1, \text {或} \lambda = 3, \text {或} \lambda = 5. \\ \end{array}
$$

##### 例3
例3 讨论下述数域  $K$  上线性方程组何时有唯一解？有无穷多个解？无解？

$$
\left\{ \begin{array}{l} x _ {1} + a x _ {2} + x _ {3} = 2, \\ x _ {1} + x _ {2} + 2 b x _ {3} = 2, \\ x _ {1} + x _ {2} - b x _ {3} = - 1. \end{array} \right.
$$

解 此方程组的系数行列式为

$$
\begin{array}{l} \left| \begin{array}{c c c} 1 & a & 1 \\ 1 & 1 & 2 b \\ 1 & 1 & - b \end{array} \right| = \left| \begin{array}{c c c} 1 & a & 1 \\ 0 & - a + 1 & - 1 + 2 b \\ 0 & - a + 1 & - 1 - b \end{array} \right| \\ = \left| \begin{array}{c c} - a + 1 & - 1 + 2 b \\ - a + 1 & - 1 - b \end{array} \right| = \left| \begin{array}{c c} - a + 1 & - 1 + 2 b \\ 0 & - 3 b \end{array} \right| \\ = (- a + 1) (- 3 b) = 3 (a - 1) b. \\ \end{array}
$$

于是上述线性方程组有唯一解

$$
\begin{array}{l} \Longleftrightarrow 3 (a - 1) b \neq 0, \\ \Longleftrightarrow a \neq 1 \text {且} b \neq 0. \\ \end{array}
$$

当  $a = 1$  时，对上述线性方程组的增广矩阵施行初等行变换化成阶梯形矩阵：

$$
\begin{array}{l} \left(\begin{array}{c c c c}1&1&1&2\\1&1&2 b&2\\1&1&- b&- 1\end{array}\right)\rightarrow \left(\begin{array}{c c c c}1&1&1&2\\0&0&2 b - 1&0\\0&0&- b - 1&- 3\end{array}\right) \\ \rightarrow \left(\begin{array}{c c c c}1&1&1&2\\0&0&- 3&- 6\\0&0&- b - 1&- 3\end{array}\right)\rightarrow \left(\begin{array}{c c c c}1&1&1&2\\0&0&1&2\\0&0&- b - 1&- 3\end{array}\right) \\ \rightarrow \left(\begin{array}{c c c c}1&1&1&2\\0&0&1&2\\0&0&0&2 b - 1\end{array}\right) \\ \end{array}
$$

当  $2b - 1 \neq 0$ ，即  $b \neq \frac{1}{2}$  时，相应的阶梯形方程组出现“ $0 = 2b - 1$ ”这个方程，从而原线性方程组无解；当  $2b - 1 = 0$ ，即  $b = \frac{1}{2}$  时，原线性方程组有无穷多个解。

当  $b = 0$  时，对原方程组的增广矩阵施行初等行变换：

$$
\begin{array}{l} \left(\begin{array}{c c c c}1&a&1&2\\1&1&0&2\\1&1&0&- 1\end{array}\right)\rightarrow \left(\begin{array}{c c c c}1&1&0&- 1\\1&1&0&2\\1&a&1&2\end{array}\right) \\ \rightarrow \left(\begin{array}{c c c c}1&1&0&- 1\\0&0&0&3\\0&a - 1&1&3\end{array}\right)\rightarrow \left(\begin{array}{c c c c}1&1&0&- 1\\0&a - 1&1&3\\0&0&0&3\end{array}\right) \\ \end{array}
$$

无论  $a$  取何值，最后一个矩阵都是阶梯形矩阵。由于相应的阶梯形方程组出现“ $0 = 3$ ”这个方程，因此原方程组无解。

综上所述，当  $a \neq 1$  且  $b \neq 0$  时，原线性方程组有唯一解；当  $a = 1$  且  $b = \frac{1}{2}$  时，原线性方程组有无穷多个解；当  $a = 1$  且  $b \neq \frac{1}{2}$  时，原线性方程组无解；当  $b = 0$  时，原线性方程组也无解。

点评：像例3那样，对系数带有字母的线性方程组讨论字母取何值时，方程组有唯一解？有无穷多个解？无解？通常的做法是先计算方程组的系数行列式；然后确定方程组有唯一解时当且仅当字母不能取哪些值；最后讨论字母取这些值时，方程组是有无穷多个解还是无解。这一步通常是把方程组的增广矩阵经过初等行变换化成阶梯形矩阵后来讨论。

思考：建立平面直角坐标系，分别考虑例3的线性方程组有唯一解，有无穷多个解，无解时，坐标为  $(a,b)$  的点组成的集合是什么样子？

### 习题2.5

##### 题1
1. 判断下述数域  $K$  上线性方程组有无解，如果有解的话，有多少解？

$$
\left\{ \begin{array}{l} x _ {1} + 4 x _ {2} + 9 x _ {3} = b _ {1}, \\ x _ {1} + 8 x _ {2} + 2 7 x _ {3} = b _ {2}, \\ x _ {1} + 1 6 x _ {2} + 8 1 x _ {3} = b _ {3}. \end{array} \right.
$$

##### 题2
2. 判断下述数域  $K$  上线性方程组有无解，如果有解的话，有多少解？

$$
\left\{ \begin{array}{c} a _ {1} ^ {2} x _ {1} + a _ {2} ^ {2} x _ {2} + \dots + a _ {n} ^ {2} x _ {n} = b _ {1}, \\ a _ {1} ^ {3} x _ {1} + a _ {2} ^ {3} x _ {2} + \dots + a _ {n} ^ {3} x _ {n} = b _ {2}, \\ \dots \quad \dots \quad \dots \quad \dots \quad \dots \\ a _ {1} ^ {n + 1} x _ {1} + a _ {2} ^ {n + 1} x _ {2} + \dots + a _ {n} ^ {n + 1} x _ {n} = b _ {n}, \end{array} \right.
$$

其中  $a_1, a_2, \dots, a_n$  是两两不等的非零数。

##### 题3
3. 当  $\lambda$  取什么值时，下述齐次线性方程组有非零解？

$$
\left\{ \begin{array}{r l} (\lambda - 2) x _ {1} & - 3 x _ {2} \\ - x _ {1} + (\lambda - 8) x _ {2} & - 2 x _ {3} = 0, \\ 2 x _ {1} & + 1 4 x _ {2} + (\lambda + 3) x _ {3} = 0. \end{array} \right.
$$

##### 题4
4. 当  $a, b$  取什么值时，下述齐次线性方程组有非零解？

$$
\left\{ \begin{array}{l} a x _ {1} + x _ {2} + x _ {3} = 0, \\ x _ {1} + b x _ {2} + x _ {3} = 0, \\ x _ {1} + 2 b x _ {2} + x _ {3} = 0. \end{array} \right.
$$

##### 题5
5. 当  $a, b$  取什么值时，下述数域  $K$  上线性方程组有唯一解？有无穷多个解？无解？

$$
\left\{ \begin{array}{l} a x _ {1} + x _ {2} + x _ {3} = 2, \\ x _ {1} + b x _ {2} + x _ {3} = 1, \\ x _ {1} + 2 b x _ {2} + x _ {3} = 2. \end{array} \right.
$$

##### 题6
6. 讨论下述数域  $K$  上线性方程组何时有唯一解？有无穷多个解？无解？

$$
\left\{ \begin{array}{l} a x _ {1} + x _ {2} + x _ {3} = 2, \\ x _ {1} + b x _ {2} + x _ {3} = 1, \\ x _ {1} + 2 b x _ {2} + x _ {3} = 1. \end{array} \right.
$$

## 2.6 行列式按  $k$  行(列)展开

### 2.6.1 内容精华

行列式可以按一行(列)展开，能不能按  $k$  行(列)展开？这首先需要  $k$  阶子式和它的

余子式的概念。

##### 定义1
定义1  $n$  阶行列式  $|A|$  中任意取定  $k$  行、 $k$  列  $(1 \leqslant k < n)$ ，位于这些行和列的交叉处的  $k^2$  个元素按原来的排法组成的  $k$  阶行列式，称为  $|A|$  的一个  $k$  阶子式。取定  $|A|$  的第  $i_1, i_2, \dots, i_k$  行  $(i_1 < i_2 < \dots < i_k)$ ，第  $j_1, j_2, \dots, j_k$  列  $(j_1 < j_2 < \dots < j_k)$ ，所得到的  $k$  阶子式记作

$$
A \binom {i _ {1}, i _ {2}, \dots , i _ {k}} {j _ {1}, j _ {2}, \dots , j _ {k}}. \tag {1}
$$

划去这个  $k$  阶子式所在的行和列，剩下的元素按原来的排法组成的  $(n - k)$  阶行列式，称为子式(1)的余子式，它前面乘以

$$
(- 1) ^ {\left(i _ {1} + i _ {2} + \dots + i _ {k}\right) + \left(j _ {1} + j _ {2} + \dots + j _ {k}\right)},
$$

则称为子式(1)的代数余子式。令

$$
\begin{array}{l} \left\{i _ {1} ^ {\prime}, i _ {2} ^ {\prime}, \dots , i _ {n - k} ^ {\prime} \right\} = \left\{1, 2, \dots , n \right\} \backslash \left\{i _ {1}, i _ {2}, \dots , i _ {k} \right\}, \\ \left\{j _ {1} ^ {\prime}, j _ {2} ^ {\prime}, \dots , j _ {n - k} ^ {\prime} \right\} = \left\{1, 2, \dots , n \right\} \backslash \left\{j _ {1}, j _ {2}, \dots , j _ {k} \right\}, \\ \end{array}
$$

并且  $i_1' < i_2' < \dots < i_{n-k}', j_1' < j_2' < \dots < j_{n-k}'$ ，则子式(1)的余子式为

$$
A \binom {i _ {1} ^ {\prime}, i _ {2} ^ {\prime}, \dots , i _ {n - k} ^ {\prime}} {j _ {1} ^ {\prime}, j _ {2} ^ {\prime}, \dots , j _ {n - k} ^ {\prime}}. \tag {2}
$$

##### 定理1
定理1(Laplace定理）在  $n$  阶行列式  $|A|$  中，取定第  $i_1,i_2,\dots ,i_k$  行  $(i_{1} < i_{2} < \dots < i_{k})$  ，则这  $k$  行元素形成的所有  $k$  阶子式与它们自己的代数余子式的乘积之和等于  $|A|$  ，即

$$
| A | = \sum_ {1 \leqslant j _ {1} <   j _ {2} <   \dots <   j _ {k} \leqslant n} A \binom {i _ {1}, i _ {2}, \dots , i _ {k}} {j _ {1}, j _ {2}, \dots , j _ {k}} (- 1) ^ {(i _ {1} + \dots + i _ {k}) + (j _ {1} + \dots + j _ {k})} A \binom {i _ {1} ^ {\prime}, i _ {2} ^ {\prime}, \dots , i _ {n - k} ^ {\prime}} {j _ {1} ^ {\prime}, j _ {2} ^ {\prime}, \dots , j _ {n - k} ^ {\prime}}. \tag {3}
$$

证明 (3)式左端  $|A|$  是  $n!$  项的代数和，现在来看右端是多少项的代数和。右端的连加号中共有  $C_n^k$  个乘积项。在每个乘积项中， $k$  阶子式有  $k!$  项，它的余子式有  $(n - k)!$  项，于是它们的乘积有  $k!(n - k)!$  项。因此右端的项数为

$$
C _ {n} ^ {k} k! (n - k)! = \frac {n !}{k ! (n - k) !} k! (n - k)! = n!.
$$

这  $n!$  项两两不同。如果能证明右端的每一项都是  $|A|$  的一项，那么右端的  $n!$  项的和正好是  $|A|$  。

在(3)式右端中任取一项：

$$
\begin{array}{l} (- 1) ^ {\tau \left(\mu_ {1} \mu_ {2} \dots \mu_ {k}\right)} a _ {i _ {1} \mu_ {1}} a _ {i _ {2} \mu_ {2}} \dots a _ {i _ {k} \mu_ {k}} \cdot (- 1) ^ {\left(i _ {1} + \dots + i _ {k}\right) + \left(j _ {1} + \dots + j _ {k}\right)} \\ \cdot (- 1) ^ {\tau \left(v _ {1} v _ {2} \dots v _ {n - k}\right)} a _ {i _ {1} ^ {\prime} v _ {1}} a _ {i _ {2} ^ {\prime} v _ {2}} \dots a _ {i _ {n - k} ^ {\prime} v _ {n - k}}, \tag {4} \\ \end{array}
$$

其中  $\mu_1\mu_2\dots \mu_k$  是  $j_{1},j_{2},\dots ,j_{k}$  的一个  $\pmb{k}$  元排列，  $v_{1}v_{2}\dots v_{n - k}$  是  $j^{\prime}_{1},j^{\prime}_{2},\dots ,j^{\prime}_{n - k}$  的一个  $\pmb {n} - \pmb{k}$  元排列。

在(3)式左端有如下一项：

$$
(- 1) ^ {\tau \left(i _ {1} \dots i _ {k} i _ {1} ^ {\prime} \dots i _ {n - k} ^ {\prime}\right) + \tau \left(\mu_ {1} \dots \mu_ {k} v _ {1} \dots v _ {n - k}\right)} a _ {i _ {1} \mu_ {1}} \dots a _ {i _ {k} \mu_ {k}} a _ {i _ {1} ^ {\prime} v _ {1}} \dots a _ {i _ {n - k} ^ {\prime} v _ {n - k}}. \tag {5}
$$

根据2.1节典型例题的例5的结果，有

$$
\begin{array}{l} (- 1) ^ {\tau \left(i _ {1} \dots i _ {k} i _ {1} ^ {\prime} \dots i _ {n - k} ^ {\prime}\right) + \tau \left(\mu_ {1} \dots \mu_ {k} v _ {1} \dots v _ {n - k}\right)} \\ = (- 1) \sum_ {r = 1} ^ {k} i _ {r} + \frac {k (1 + k)}{2} (- 1) ^ {\tau (\mu_ {1} \dots \mu_ {k}) + \tau (v _ {1} \dots v _ {n - k}) + \sum_ {r = 1} ^ {k} j _ {r} + \frac {k (1 + k)}{2}} \\ = (- 1) ^ {\left(i _ {1} + \dots + i _ {k}\right) + \left(j _ {1} + \dots + j _ {k}\right)} (- 1) ^ {\tau \left(\mu_ {1} \dots \mu_ {k}\right) + \tau \left(v _ {1} \dots v _ {n - k}\right)}. \\ \end{array}
$$

因此(5)式与(4)式相等。这证明了(3)式右端的每一项都是左端  $|A|$  的一项。从而(3)式

成立。

定理1称为拉普拉斯(Laplace)定理(或行列式按  $k$  行展开定理）。

把定理1中的“行”换成“列”仍然成立，称为行列式按  $k$  列展开定理。

##### 推论1
推论1 下式成立：

$$
\left| \begin{array}{c c c c c c} a _ {1 1} & \dots & a _ {1 k} & 0 & \dots & 0 \\ \vdots & & \vdots & \vdots & & \vdots \\ a _ {k 1} & \dots & a _ {k k} & 0 & \dots & 0 \\ c _ {1 1} & \dots & c _ {1 k} & b _ {1 1} & \dots & b _ {1 r} \\ \vdots & & \vdots & \vdots & & \vdots \\ c _ {r 1} & \dots & c _ {r k} & b _ {r 1} & \dots & b _ {r r} \end{array} \right| = \left| \begin{array}{c c c} a _ {1 1} & \dots & a _ {1 k} \\ \vdots & & \vdots \\ a _ {k 1} & \dots & a _ {k k} \end{array} \right| \cdot \left| \begin{array}{c c c} b _ {1 1} & \dots & b _ {1 r} \\ \vdots & & \vdots \\ b _ {r 1} & \dots & b _ {r r} \end{array} \right|. \tag {6}
$$

证明 把(6)式左端的行列式按前  $k$  行展开, 这  $k$  行元素形成的  $k$  阶子式中, 只有左上角的  $k$  阶子式的值可能不为 0 , 其余的  $k$  阶子式一定包含零列, 从而其值为 0 。左上角的  $k$  阶子式的余子式正好是右下角的  $r$  阶子式, 并且  $(-1)^{(1 + 2 + \cdots + k) + (1 + 2 + \cdots + k)} = 1$  。因此(6)式成立。

令

$$
A = \left( \begin{array}{c c c} a _ {1 1} & \dots & a _ {1 k} \\ \vdots & & \vdots \\ a _ {k 1} & \dots & a _ {k k} \end{array} \right), B = \left( \begin{array}{c c c} b _ {1 1} & \dots & b _ {1 r} \\ \vdots & & \vdots \\ b _ {r 1} & \dots & b _ {r r} \end{array} \right),
$$

$$
C = \left( \begin{array}{c c c} c _ {1 1} & \dots & c _ {1 k} \\ \vdots & & \vdots \\ c _ {r 1} & \dots & c _ {r k} \end{array} \right), 0 = \left( \begin{array}{c c c} 0 & \dots & 0 \\ \vdots & & \vdots \\ 0 & \dots & 0 \end{array} \right),
$$

则(6)式可以简写成

$$
\left| \begin{array}{l l} A & 0 \\ C & B \end{array} \right| = | A | | B |. \tag {7}
$$

公式(7)是非常有用的。

### 2.6.2 典型例题

##### 例1
例1 计算行列式：

$$
\left| \begin{array}{c c c c c c} 0 & \dots & 0 & a _ {1 1} & \dots & a _ {1 k} \\ \vdots & & \vdots & \vdots & & \vdots \\ 0 & \dots & 0 & a _ {k 1} & \dots & a _ {k k} \\ b _ {1 1} & \dots & b _ {1 r} & c _ {1 1} & \dots & c _ {1 k} \\ \vdots & & \vdots & \vdots & & \vdots \\ b _ {r 1} & \dots & b _ {m} & c _ {r 1} & \dots & c _ {r k} \end{array} \right|. \tag {8}
$$

解 把行列式(8)按前  $k$  行展开，得

$$
\text {原 式} = \left| \begin{array}{c c c} a _ {1 1} & \dots & a _ {1 k} \\ \vdots & & \vdots \\ a _ {k 1} & \dots & a _ {k k} \end{array} \right| \cdot (- 1) ^ {(1 + 2 + \dots + k) + [ (r + 1) + (r + 2) + \dots + (r + k) ]} \cdot \left| \begin{array}{c c c} b _ {1 1} & \dots & b _ {1 r} \\ \vdots & & \vdots \\ b _ {r 1} & \dots & b _ {r r} \end{array} \right|
$$

$$
= (- 1) ^ {k r} \left| \begin{array}{c c c} a _ {1 1} & \dots & a _ {1 k} \\ \vdots & & \vdots \\ a _ {k 1} & \dots & a _ {k k} \end{array} \right| \cdot \left| \begin{array}{c c c} b _ {1 1} & \dots & b _ {1 r} \\ \vdots & & \vdots \\ b _ {r 1} & \dots & b _ {r r} \end{array} \right|.
$$

##### 例2
例2 设  $|A|$  是关于  $1, 2, \dots, n$  的范德蒙行列式，计算  $|A|$  的前  $n - 1$  行划去第  $j$  列得到的  $n - 1$  阶子式：

$$
A \left( \begin{array}{l} 1, 2, \dots , n - 1 \\ 1, \dots , j - 1, j + 1, \dots , n \end{array} \right),
$$

其中  $j\in \{1,2,\dots ,n\}$  。

解

$$
\begin{array}{l} \mathbf {A} \binom {1, 2, \dots , n - 1} {1, \dots , j - 1, j + 1, \dots , n} = \left| \begin{array}{c c c c c c c} 1 & 1 & \dots & 1 & 1 & \dots & 1 \\ 1 & 2 & \dots & j - 1 & j + 1 & \dots & n \\ 1 ^ {2} & 2 ^ {2} & \dots & (j - 1) ^ {2} & (j + 1) ^ {2} & \dots & n ^ {2} \\ \vdots & \vdots & & \vdots & \vdots & & \vdots \\ 1 ^ {n - 2} & 2 ^ {n - 2} & \dots & (j - 1) ^ {n - 2} & (j + 1) ^ {n - 2} & \dots & n ^ {n - 2} \end{array} \right| \\ = (2 - 1) \dots [ (j - 1) - 1 ] [ (j + 1) - 1 ] \dots (n - 1) \cdot (3 - 2) \dots \\ [ (j - 1) - 2 ] [ (j + 1) - 2 ] (n - 2) \cdot (4 - 3) \dots [ (j - 1) - 3 ] [ (j + 1) - 3 ] \dots \\ (n - 3) \cdot \dots [ (j + 1) - (j - 1) ] \dots [ n - (j - 1) ] [ (j + 2) - (j + 1) ] \cdot \dots \\ [ n - (j + 1) ] \cdot \dots [ n - (n - 1) ] \\ = \frac {(n - 1) ! (n - 2) ! (n - 3) ! \cdots (n - j + 2) ! (n - j + 1) ! (n - j - 1) ! \cdots 2 ! 1 !}{(j - 1) (j - 2) (j - 3) \cdots 2 \cdot 1} \\ = \frac {(n - 1) !}{(j - 1) ! (n - j) !} \prod_ {k = 1} ^ {n - 2} k! = C _ {n - 1} ^ {j - 1} \prod_ {k = 1} ^ {n - 2} k!. \\ \end{array}
$$

##### 例3
例3 计算下述  $2n$  阶行列式（主对角线上元素都是  $a$  ，反对角线上元素都是  $b$  ，空缺处的元素为0）：

$$
D _ {2 n} = \left| \begin{array}{c c c c c c} a & & & & & b \\ & \ddots & & & \ddots \\ & & a & b & & \\ & & b & a & & \\ & \ddots & & & \ddots \\ b & & & & & a \end{array} \right|.
$$

解 每次都按第1行和最后一行展开，得

$$
\begin{array}{l} D _ {2 n} = \left| \begin{array}{l l} a & b \\ b & a \end{array} \right| (- 1) ^ {(1 + 2 n) + (1 + 2 n)} \cdot D _ {2 n - 2} \\ = \left(a ^ {2} - b ^ {2}\right) \left| \begin{array}{l l} a & b \\ b & a \end{array} \right| (- 1) ^ {\left[ 1 + (2 n - 2) \right] + \left[ 1 + (2 n - 2) \right]} \cdot D _ {2 n - 4} \\ = (a ^ {2} - b ^ {2}) ^ {2} D _ {2 n - 4} \\ \dots \\ = (a ^ {2} - b ^ {2}) ^ {n - 1} D _ {2} = (a ^ {2} - b ^ {2}) ^ {n}. \\ \end{array}
$$

### 习题2.6

##### 题1
1. 计算行列式：

$$
\left| \begin{array}{c c c c c} 2 & 3 & 0 & 0 & 0 \\ - 1 & 4 & 0 & 0 & 0 \\ 3 7 & 8 5 & 1 & 2 & 0 \\ 2 9 & 7 3 & 0 & 3 & 4 \\ 1 9 & 6 7 & 1 & 0 & 2 \end{array} \right|.
$$

##### 题2
2. 计算行列式：

$$
\left| \begin{array}{c c c c c c} a _ {1 1} & \dots & a _ {1 k} & c _ {1 1} & \dots & c _ {1 r} \\ \vdots & & \vdots & \vdots & & \vdots \\ a _ {k 1} & \dots & a _ {k k} & c _ {k 1} & \dots & c _ {k r} \\ 0 & \dots & 0 & b _ {1 1} & \dots & b _ {1 r} \\ \vdots & & \vdots & \vdots & & \vdots \\ 0 & \dots & 0 & b _ {r 1} & \dots & b _ {r r} \end{array} \right|.
$$

##### 题3
3. 设  $|A|$  是关于  $1,2,\dots,n$  的范德蒙行列式，计算：

(1)  $A\left( \begin{array}{l} 1, 2, \dots , n - 1 \\ 2, 3, \dots , n \end{array} \right)$ ;

(2)  $A\binom{1,2,\cdots,n-1}{1,3,\cdots,n}$ .

**补充题二**

##### 题1
1. 在空间右手直角坐标系  $[0; e_1, e_2, e_3]$  中，两个非零向量  $a, b$  的坐标分别为  $(a_1, a_2, 0), (b_1, b_2, 0)$ 。

（1）求以  $a, b$  为邻边的平行四边形的面积，并且把结果用一个行列式表示；

（2）求以  $a, b$  为两边的三角形的面积，并且把结果用一个行列式表示。

解（1）以  $a, b$  为邻边的平行四边形的面积  $S_{1}$  为

$$
S _ {1} = | \boldsymbol {a} | | \boldsymbol {b} | \sin \langle \boldsymbol {a}, \boldsymbol {b} \rangle = | \boldsymbol {a} \times \boldsymbol {b} |
$$

由于  $\pmb{a} \times \pmb{b} = (a_{1}\pmb{e}_{1} + a_{2}\pmb{e}_{2}) \times (b_{1}\pmb{e}_{1} + b_{2}\pmb{e}_{2}) = (a_{1}b_{2} - a_{2}b_{1})\pmb{e}_{3}$ ,

因此  $S_{1} = \left|(a_{1}b_{2} - a_{2}b_{1})e_{3}\right| = \left|a_{1}b_{2} - a_{2}b_{1}\right| = \left|\left| \begin{array}{cc}a_{1} & b_{1}\\ a_{2} & b_{2} \end{array} \right|\right|$

（2）以  $\pmb{a},\pmb{b}$  为两边的三角形的面积  $S_{2}$  等于以  $\pmb{a},\pmb{b}$  为邻边的平行四边形的面积  $S_{1}$  的一半，因此

$$
S _ {2} = \frac {1}{2} \left| \left| \begin{array}{l l} a _ {1} & b _ {1} \\ a _ {2} & b _ {2} \end{array} \right| \right|.
$$

##### 题2
2. 在空间右手直角坐标系  $[0; e_1, e_2, e_3]$  中，三个非零向量  $a, b, c$  的坐标分别为

$$
\left(a _ {1}, a _ {2}, a _ {3}\right), \left(b _ {1}, b _ {2}, b _ {3}\right), \left(c _ {1}, c _ {2}, c _ {3}\right).
$$

求以  $a, b, c$  为棱的平行六面体的体积，并且把结果用一个行列式表示。

解 以  $a, b, c$  为棱的平行六面体的体积  $V$  为

$$
\begin{array}{l} V = | \boldsymbol {a} \times \boldsymbol {b} | | \boldsymbol {c} | | \cos \langle \boldsymbol {c}, \boldsymbol {a} \times \boldsymbol {b} \rangle | \\ = | \boldsymbol {a} \times \boldsymbol {b} \cdot \boldsymbol {c} |. \\ \end{array}
$$

由于

$$
\begin{array}{l} \boldsymbol {a} \times \boldsymbol {b} = \left(a _ {1} \boldsymbol {e} _ {1} + a _ {2} \boldsymbol {e} _ {2} + a _ {3} \boldsymbol {e} _ {3}\right) \times \left(b _ {1} \boldsymbol {e} _ {1} + b _ {2} \boldsymbol {e} _ {2} + b _ {3} \boldsymbol {e} _ {3}\right) \\ = a _ {1} b _ {2} e _ {3} - a _ {1} b _ {3} e _ {2} - a _ {2} b _ {1} e _ {3} + a _ {2} b _ {3} e _ {1} + a _ {3} b _ {1} e _ {2} - a _ {3} b _ {2} e _ {1} \\ = \left| \begin{array}{l l} a _ {2} & b _ {2} \\ a _ {3} & b _ {3} \end{array} \right| \boldsymbol {e} _ {1} - \left| \begin{array}{l l} a _ {1} & b _ {1} \\ a _ {3} & b _ {3} \end{array} \right| \boldsymbol {e} _ {2} + \left| \begin{array}{l l} a _ {1} & b _ {1} \\ a _ {2} & b _ {2} \end{array} \right| \boldsymbol {e} _ {3} \\ \end{array}
$$

因此

$$
\begin{array}{l} \boldsymbol {a} \times \boldsymbol {b} \cdot \boldsymbol {c} = \left| \begin{array}{l l} a _ {2} & b _ {2} \\ a _ {3} & b _ {3} \end{array} \right| c _ {1} - \left| \begin{array}{l l} a _ {1} & b _ {1} \\ a _ {3} & b _ {3} \end{array} \right| c _ {2} + \left| \begin{array}{l l} a _ {1} & b _ {1} \\ a _ {2} & b _ {2} \end{array} \right| c _ {3} \\ = \left| \begin{array}{c c c} a _ {1} & b _ {1} & c _ {1} \\ a _ {2} & b _ {2} & c _ {2} \\ a _ {3} & b _ {3} & c _ {3} \end{array} \right|. \\ \end{array}
$$

从而

$$
V = \left| \left| \begin{array}{c c c} a _ {1} & b _ {1} & c _ {1} \\ a _ {2} & b _ {2} & c _ {2} \\ a _ {3} & b _ {3} & c _ {3} \end{array} \right| \right|.
$$

点评：从第1、2题看到，由平行四边形的面积和平行六面体的体积引出了二阶行列式和三阶行列式。一个二阶行列式可以表示以它的第1、2列为坐标的两个向量张成的平行四边形的定向面积；一个三阶行列式可以表示以它的第1、2、3列为坐标的三个向量张成的平行六面体的定向体积。这就是二阶行列式和三阶行列式的几何意义。

##### 题3
3. 求元素为 1 或 0 的三阶行列式可取到的最大值。

解为了使元素为1或0的三阶行列式取到最大值，应该尽可能使带正号的项其3个元素的乘积为1,带负号的项其3个元素的乘积为0。如果行列式的三个带正号的项全等于1,那么这个三阶行列式的元素全为1,此时两行相等,行列式的值为0。考虑两个带正号的项等于1,三个带负号的项其3个元素的乘积为0,此时行列式的值为2。例如

$$
\left| \begin{array}{l l l} 0 & 1 & 1 \\ 1 & 0 & 1 \\ 1 & 1 & 0 \end{array} \right| = 1 + 1 = 2.
$$

因此元素为1或0的三阶行列式可取到的最大值为2。

##### 题4
4. 求元素为 1 或 -1 的三阶行列式可取到的最大值。

解 据习题2.2的第6题的结果，元素为1或-1的三阶行列式的值必为偶数。

由于三阶行列式共有6项，且由于其元素为1或-1，因此这6项或为1，或为-1。假设这6项全为1，则行列式的值为6。此时有

$$
\begin{array}{l} a _ {1 1} a _ {2 2} a _ {3 3} = 1, \quad a _ {1 2} a _ {2 3} a _ {3 1} = 1, \quad a _ {1 3} a _ {2 1} a _ {3 2} = 1, \\ - a _ {1 3} a _ {2 2} a _ {3 1} = 1, - a _ {1 2} a _ {2 1} a _ {3 3} = 1, - a _ {1 1} a _ {2 3} a _ {3 2} = 1. \\ \end{array}
$$

由此得出

$$
\begin{array}{l} a _ {1 1} a _ {2 2} a _ {3 3} a _ {1 2} a _ {2 3} a _ {3 1} a _ {1 3} a _ {2 1} a _ {3 2} = 1, \\ a _ {1 3} a _ {2 2} a _ {3 1} a _ {1 2} a _ {2 1} a _ {3 3} a _ {1 1} a _ {2 3} a _ {3 2} = - 1. \\ \end{array}
$$

上述两个等式的左边都是三阶行列式的9个元素的乘积，于是得出矛盾。因此元素为1或  $-1$  的三阶行列式的值不可能等于6。

$$
\left| \begin{array}{r r r} - 1 & 1 & 1 \\ 1 & - 1 & 1 \\ 1 & 1 & - 1 \end{array} \right| = (- 1) + 1 + 1 - (- 1) - (- 1) - (- 1) = 4.
$$

这表明元素为1或-1的三阶行列式可取到最大值为4。

思考：元素为1或一1的三阶行列式的值可不可能等于一6？

##### 题5
5. 设  $n \geqslant 3$ , 证明: 元素为 1 或 -1 的  $n$  阶行列式的绝对值不超过  $(n-1)!(n-1)$ 。

证明 从第4题和它后面的思考题可知，元素为1或-1的三阶行列式的绝对值不超过  $4 = (3 - 1)!(3 - 1)$ 。

假设对于元素为1或-1的  $n - 1$  阶行列式命题为真。现在来看元素为1或-1的  $n$  阶行列式  $|A|$  。把  $|A|$  按第1行展开，得

$$
| A | = a _ {1 1} A _ {1 1} + a _ {1 2} A _ {1 2} + \dots + a _ {1 n} A _ {1 n}.
$$

由于  $a_{1j} = \pm 1$  ，且  $(-1)^{1 + j}A_{1j}$  是元素为1或-1的  $n - 1$  阶行列式，因此据归纳假设，得

$$
\begin{array}{l} \left| \left| A \right| \right| = \left| a _ {1 1} A _ {1 1} + a _ {1 2} A _ {1 2} + \dots + a _ {1 n} A _ {1 n} \right| \\ \leqslant \left| a _ {1 1} \right| \left| A _ {1 1} \right| + \left| a _ {1 2} \right| \left| A _ {1 2} \right| + \dots + \left| a _ {1 n} \right| \left| A _ {1 n} \right| \\ \leqslant (n - 2)! (n - 2) n = (n - 1)! \frac {(n - 2) n}{n - 1} \\ <   (n - 1)! (n - 1) \\ \end{array}
$$

##### 题6
6. 求元素为 1 或 -1 的 4 阶行列式可取到的最大值。

解 从第5题的证明过程可以看到：元素为1或-1的4阶行列式的绝对值不超过 $(4 - 2)!(4 - 2)4 = 16$ 。

$$
\begin{array}{l} \left| \begin{array}{r r r r} 1 & 1 & 1 & 1 \\ 1 & - 1 & 1 & - 1 \\ 1 & 1 & - 1 & - 1 \\ 1 & - 1 & - 1 & 1 \end{array} \right| = \left| \begin{array}{r r r r} 1 & 1 & 1 & 1 \\ 0 & - 2 & 0 & - 2 \\ 0 & 0 & - 2 & - 2 \\ 0 & - 2 & - 2 & 0 \end{array} \right| \\ = \left| \begin{array}{r r r} - 2 & 0 & - 2 \\ 0 & - 2 & - 2 \\ - 2 & - 2 & 0 \end{array} \right| = \left| \begin{array}{r r r} - 2 & 0 & - 2 \\ 0 & - 2 & - 2 \\ 0 & - 2 & 2 \end{array} \right| = 1 6. \\ \end{array}
$$

因此元素为1或-1的4阶行列式可取到的最大值为16。

##### 题7
7. 设  $n \geqslant 2$ . 证明：元素为1或-1的  $n$  阶行列式的值能被  $2^{n-1}$  整除。

证明 设  $|A|$  是元素为 1 或 -1 的  $n$  阶行列式  $(n \geqslant 2)$  。把  $|A|$  的第 1 列中元素为 -1 的行提取公因子 -1, 得

$$
\begin{array}{l} | A | = (- 1) ^ {m} \left| \begin{array}{c c c c} 1 & b _ {1 2} & \dots & b _ {1 n} \\ 1 & b _ {2 2} & \dots & b _ {2 n} \\ \vdots & \vdots & & \vdots \\ 1 & b _ {n 2} & \dots & b _ {m} \end{array} \right| = (- 1) ^ {m} \left| \begin{array}{c c c c} 1 & b _ {1 2} & \dots & b _ {1 n} \\ 0 & c _ {2 2} & \dots & c _ {2 n} \\ \vdots & \vdots & & \vdots \\ 0 & c _ {n 2} & \dots & c _ {m} \end{array} \right| \\ = (- 1) ^ {m} \left| \begin{array}{c c c} c _ {2 2} & \dots & c _ {2 n} \\ \vdots & & \vdots \\ c _ {n 2} & \dots & c _ {m} \end{array} \right| = (- 1) ^ {m} 2 ^ {n - 1} \left| \begin{array}{c c c} d _ {2 2} & \dots & b _ {2 n} \\ \vdots & & \vdots \\ d _ {n 2} & \dots & d _ {m} \end{array} \right|, \\ \end{array}
$$

其中最后一步是由于  $c_{ij}$  为2，或一2，或0，因此每一列可提出公因子2。此时  $d_{ij}$  为1,或-1,或0。从而最后一个  $n - 1$  阶行列式的值为整数。因此  $|\pmb{A}|$  能被  $2^{n - 1}$  整除。

**应用小天地:行列式的应用举例**

例1斐波那契(Fibonacci)数列是

$$
1, 2, 3, 5, 8, 1 3, 2 1, 3 5, \dots
$$

它满足：  $F_{n} = F_{n - 1} + F_{n - 2}(n\geqslant 3)$  ，  $F_{1} = 1,F_{2} = 2$

（1）证明 Fibonacci 数列的通项  $\pmb{F}_{n}$  可由下述行列式表示：

$$
\boldsymbol {F} _ {n} = \left| \begin{array}{c c c c c c c c c} 1 & - 1 & 0 & 0 & \dots & 0 & 0 & 0 \\ 1 & 1 & - 1 & 0 & \dots & 0 & 0 & 0 \\ 0 & 1 & 1 & - 1 & \dots & 0 & 0 & 0 \\ \vdots & \vdots & \vdots & \vdots & & \vdots & \vdots & \vdots \\ 0 & 0 & 0 & 0 & \dots & 1 & 1 & - 1 \\ 0 & 0 & 0 & 0 & \dots & 0 & 1 & 1 \end{array} \right|;
$$

（2）求 Fibonacci 数列的通项公式。

（1）证明 把上述  $n$  阶行列式按第1列展开，得

$$
\boldsymbol {F} _ {n} = \boldsymbol {F} _ {n - 1} + 1 \cdot (- 1) ^ {2 + 1} (- 1) \boldsymbol {F} _ {n - 2} = \boldsymbol {F} _ {n - 1} + \boldsymbol {F} _ {n - 2}. (n \geqslant 3)
$$

上述形式的1阶行列式的值为1,2阶行列式的值为2。因此Fibonacci数列的通项  $\pmb{F}_{n}$  可由上述行列式表示。

(2) 解 令  $\alpha + \beta = 1, \alpha \beta = -1$ ，则  $\alpha, \beta$  是方程

$$
x ^ {2} - x - 1 = 0
$$

的两个根：

$$
\alpha = \frac {1 + \sqrt {5}}{2}, \quad \beta = \frac {1 - \sqrt {5}}{2}.
$$

于是

$$
\boldsymbol {F} _ {n} = \left| \begin{array}{c c c c c c c} \alpha + \beta & \alpha \beta & 0 & \dots & 0 & 0 & 0 \\ 1 & \alpha + \beta & \alpha \beta & \dots & 0 & 0 & 0 \\ 0 & 1 & \alpha + \beta & \dots & 0 & 0 & 0 \\ \vdots & \vdots & \vdots & & \vdots & \vdots & \vdots \\ 0 & 0 & 0 & \dots & 1 & \alpha + \beta & \alpha \beta \\ 0 & 0 & 0 & \dots & 0 & 1 & \alpha + \beta \end{array} \right|.
$$

根据本章2.4节的典型例题的例6，得

$$
\boldsymbol {F} _ {n} = \frac {\alpha^ {n + 1} - \beta^ {n + 1}}{\alpha - \beta} = \frac {1}{\sqrt {5}} \left[ \left(\frac {1 + \sqrt {5}}{2}\right) ^ {n + 1} - \left(\frac {1 - \sqrt {5}}{2}\right) ^ {n + 1} \right].
$$

##### 例2
例2 设  $f_{ij}(t)$  是可微函数， $1 \leqslant i, j \leqslant n$ 。令

$$
F (t) = \left| \begin{array}{c c c c} f _ {1 1} (t) & f _ {1 2} (t) & \dots & f _ {1 n} (t) \\ f _ {2 1} (t) & f _ {2 2} (t) & \dots & f _ {2 n} (t) \\ \vdots & \vdots & & \vdots \\ f _ {n 1} (t) & f _ {n 2} (t) & \dots & f _ {m} (t) \end{array} \right|.
$$

证明：

$$
\frac {\mathrm {d}}{\mathrm {d} t} F (t) = \sum_ {j = 1} ^ {n} \left| \begin{array}{c c c c c c} f _ {1 1} (t) & f _ {1 2} (t) & \dots & \frac {\mathrm {d}}{\mathrm {d} t} f _ {1 j} (t) & \dots & f _ {1 n} (t) \\ f _ {2 1} (t) & f _ {2 2} (t) & \dots & \frac {\mathrm {d}}{\mathrm {d} t} f _ {2 j} (t) & \dots & f _ {2 n} (t) \\ \vdots & \vdots & & \vdots & & \vdots \\ f _ {n 1} (t) & f _ {n 2} (t) & \dots & \frac {\mathrm {d}}{\mathrm {d} t} f _ {n j} (t) & \dots & f _ {n n} (t) \end{array} \right|.
$$

证明

$$
\begin{array}{l} \frac {\mathrm {d}}{\mathrm {d} t} F (t) = \frac {\mathrm {d}}{\mathrm {d} t} \left[ \sum_ {i _ {1} i _ {2} \dots i _ {n}} (- 1) ^ {\tau \left(i _ {1} i _ {2} \dots i _ {n}\right)} f _ {i _ {1} 1} (t) f _ {i _ {2} 2} (t) \dots f _ {i _ {n} n} (t) \right] \\ = \sum_ {i _ {1} i _ {2} \dots i _ {n}} (- 1) ^ {\tau (i _ {1} i _ {2} \dots i _ {n})} \frac {\mathrm {d}}{\mathrm {d} t} \left[ f _ {i _ {1} 1} (t) f _ {i _ {2} 2} (t) \dots f _ {i _ {n} n} (t) \right] \\ = \sum_ {i _ {1} i _ {2} \dots i _ {n}} (- 1) ^ {\tau (i _ {1} i _ {2} \dots i _ {n})} \sum_ {j = 1} ^ {n} f _ {i _ {1} 1} (t) f _ {i _ {2} 2} (t) \dots \frac {\mathrm {d}}{\mathrm {d} t} f _ {i _ {j} j} (t) \dots f _ {i _ {n} n} (t) \\ = \sum_ {j = 1} ^ {n} \sum_ {i _ {1} i _ {2} \dots i _ {n}} (- 1) ^ {\tau \left(i _ {1} i _ {2} \dots i _ {n}\right)} f _ {i _ {1} 1} (t) f _ {i _ {2} 2} (t) \dots \frac {\mathrm {d}}{\mathrm {d} t} f _ {i _ {j} j} (t) \dots f _ {i _ {n} n} (t) \\ = \sum_ {j = 1} ^ {n} \left| \begin{array}{c c c c c c} f _ {1 1} (t) & f _ {1 2} (t) & \dots & \frac {\mathrm {d}}{\mathrm {d} t} f _ {1 j} (t) & \dots & f _ {1 n} (t) \\ f _ {2 1} (t) & f _ {2 2} (t) & \dots & \frac {\mathrm {d}}{\mathrm {d} t} f _ {2 j} (t) & \dots & f _ {2 n} (t) \\ \vdots & \vdots & & \vdots & & \vdots \\ f _ {n 1} (t) & f _ {n 2} (t) & \dots & \frac {\mathrm {d}}{\mathrm {d} t} f _ {n j} (t) & \dots & f _ {m n} (t) \end{array} \right|. \\ \end{array}
$$

##### 例3
例3 实系数三元多项式  $f(x, y, z) = x^3 + y^3 + z^3 - 3xyz$  有没有一次因式？如果有，

把它找出来。

解

$$
\begin{array}{l} x ^ {3} + y ^ {3} + z ^ {3} - 3 x y z = \left| \begin{array}{c c c} x & y & z \\ z & x & y \\ y & z & x \end{array} \right| = \left| \begin{array}{c c c} x + y + z & y & z \\ x + y + z & x & y \\ x + y + z & z & x \end{array} \right| \\ = (x + y + z) \left| \begin{array}{c c c} 1 & y & z \\ 1 & x & y \\ 1 & z & x \end{array} \right| \\ = (x + y + z) \left(x ^ {2} + y ^ {2} + z ^ {2} - x y - x z - y z\right). \\ \end{array}
$$

因此  $f(x,y,z)$  有一个一次因式  $(x + y + z)$  。

注：可以证明  $x^{2} + y^{2} + z^{2} - xy - xz - yz$  不能分解成两个一次因式的乘积。读者不妨试证之。

##### 例4
例4 将下述有理系数三元多项式  $g(x,y,z)$  因式分解：

$$
g (x, y, z) = \left| \begin{array}{c c c c} 0 & x & y & z \\ x & 0 & z & y \\ y & z & 0 & x \\ z & y & x & 0 \end{array} \right|.
$$

解 将4阶行列式的第2、3、4列都加到第1列上，第1列有公因子  $(x + y + z)$  可以提出去，因此  $g(x, y, z)$  有一个因式  $(x + y + z)$ 。

将原4阶行列式的第2列乘以1，第3、4列乘以一1，都加到第1列上，第1列有公因子  $x - y - z$  可以提出去，因此  $g(x,y,z)$  有一个因式  $(x - y - z)$  。

将原4阶行列式的第1、4列乘以一1，第3列乘以1，都加到第2列上，第2列有公因子  $x + y - z$  可以提出去，因此  $g(x,y,z)$  有一个因式  $(x + y - z)$  。

将原4阶行列式的第1、3列乘以一1，第4列乘以1，都加到第2列上，第2列有公因子  $x - y + z$  可以提出去，因此  $g(x,y,z)$  有一个因式  $(x - y + z)$  。

由于  $g(x,y,z)$  是4次多项式，因此

$$
g (x, y, z) = a (x + y + z) (x - y - z) (x + y - z) (x - y + z).
$$

为了确定  $a$  的值， $x, y, z$  分别用0,0,1代入，则4阶行列式为

$$
\left| \begin{array}{c c c c} 0 & 0 & 0 & 1 \\ 0 & 0 & 1 & 0 \\ 0 & 1 & 0 & 0 \\ 1 & 0 & 0 & 0 \end{array} \right| = (- 1) ^ {\tau (4 3 2 1)} \cdot 1 = 1.
$$

又  $g(0,0,1) = a\cdot 1\cdot (-1)\cdot (-1)\cdot 1 = a,$

因此  $a = 1$  。从而

$$
g (x, y, z) = (x + y + z) (x + y - z) (x - y + z) (x - y - z).
$$

##### 例5
例5 计算实数域上  $n$  阶三对角线行列式：

$$
D _ {n} = \left| \begin{array}{c c c c c c c c} a & b & 0 & 0 & \dots & 0 & 0 & 0 \\ c & a & b & 0 & \dots & 0 & 0 & 0 \\ 0 & c & a & b & \dots & 0 & 0 & 0 \\ \vdots & \vdots & \vdots & \vdots & & \vdots & \vdots & \vdots \\ 0 & 0 & 0 & 0 & \dots & c & a & b \\ 0 & 0 & 0 & 0 & \dots & 0 & c & a \end{array} \right|.
$$

解 若  $c = 0$  ，则  $D_{n} = a^{n}$  。下面设  $c \neq 0$  ，则

$$
D _ {n} = c ^ {n} \left| \begin{array}{c c c c c c c c} \frac {a}{c} & \frac {b}{c} & 0 & 0 & \dots & 0 & 0 & 0 \\ 1 & \frac {a}{c} & \frac {b}{c} & 0 & \dots & 0 & 0 & 0 \\ 0 & 1 & \frac {a}{c} & \frac {b}{c} & \dots & 0 & 0 & 0 \\ \vdots & \vdots & \vdots & \vdots & & \vdots & \vdots & \vdots \\ 0 & 0 & 0 & 0 & \dots & 1 & \frac {a}{c} & \frac {b}{c} \\ 0 & 0 & 0 & 0 & \dots & 0 & 1 & \frac {a}{c} \end{array} \right|.
$$

令  $\alpha +\beta = \frac{a}{c},\alpha \beta = \frac{b}{c}$  ，则  $\alpha ,\beta$  是方程

$$
x ^ {2} - \frac {a}{c} x + \frac {b}{c} = 0
$$

的两个根：

$$
\alpha = \frac {1}{2} \left[ \frac {a}{c} + \frac {1}{| c |} \sqrt {a ^ {2} - 4 b c} \right], \beta = \frac {1}{2} \left[ \frac {a}{c} - \frac {1}{| c |} \sqrt {a ^ {2} - 4 b c} \right).
$$

当  $a^2 \neq 4bc$  时， $\alpha \neq \beta$ ，利用本章2.4节典型例题的例6的结果，得

$$
D _ {n} = c ^ {n} \frac {\alpha^ {n + 1} - \beta^ {n + 1}}{\alpha - \beta} = \frac {(c \alpha) ^ {n + 1} - (c \beta) ^ {n + 1}}{c \alpha - c \beta} = \frac {\alpha_ {1} ^ {n + 1} - \beta_ {1} ^ {n + 1}}{\alpha_ {1} - \beta_ {1}},
$$

其中  $\alpha_{1} = c\alpha, \beta_{1} = c\beta$  是方程

$$
x ^ {2} - a x + b x = 0
$$

的两个根。

当  $a^2 = 4bc$  时，  $\alpha = \beta$  。利用习题2.4的第4题的结果，得

$$
D _ {n} = c ^ {n} (n + 1) \alpha^ {n} = (n + 1) (c \alpha) ^ {n} = (n + 1) \frac {a ^ {n}}{2 ^ {n}}.
$$

因此

$$
D _ {n} = \left\{ \begin{array}{l l} \frac {\alpha_ {1} ^ {n + 1} - \beta_ {1} ^ {n + 1}}{\alpha_ {1} - \beta_ {1}}, & \text {当} a ^ {2} \neq 4 b c, \\ (n + 1) \frac {a ^ {n}}{2 ^ {n}}, & \text {当} a ^ {2} = 4 b c, \end{array} \right.
$$

其中  $\alpha_{1},\beta_{1}$  是方程  $x^{2} - ax + bc = 0$  的两个根。

点评：三对角线行列式有许多应用。

##### 例6
例6 计算  $n$  阶行列式：

$$
D _ {n} = \left| \begin{array}{c c c c c c c c} 2 n & n & 0 & 0 & \dots & 0 & 0 & 0 \\ n & 2 n & n & 0 & \dots & 0 & 0 & 0 \\ 0 & n & 2 n & n & \dots & 0 & 0 & 0 \\ \vdots & \vdots & \vdots & \vdots & & \vdots & \vdots & \vdots \\ 0 & 0 & 0 & 0 & \dots & n & 2 n & n \\ 0 & 0 & 0 & 0 & \dots & 0 & n & 2 n \end{array} \right|.
$$

解 这是三对角线行列式，利用例5的结果可得

$$
D _ {n} = (n + 1) n ^ {n}.
$$

##### 例7
例7 计算  $n$  阶行列式：

$$
D _ {n} = \left| \begin{array}{c c c c c c c c} 2 \cos \alpha & 1 & 0 & 0 & \dots & 0 & 0 & 0 \\ 1 & 2 \cos \alpha & 1 & 0 & \dots & 0 & 0 & 0 \\ 0 & 1 & 2 \cos \alpha & 1 & \dots & 0 & 0 & 0 \\ \vdots & \vdots & \vdots & \vdots & & \vdots & \vdots & \vdots \\ 0 & 0 & 0 & 0 & \dots & 1 & 2 \cos \alpha & 1 \\ 0 & 0 & 0 & 0 & \dots & 0 & 1 & 2 \cos \alpha \end{array} \right|.
$$

解 这是三对角线行列式，利用例5的结果可得

$$
D _ {n} = \left\{ \begin{array}{l l} \frac {\sin (n + 1) \alpha}{\sin \alpha}, & \text {当} \alpha \neq k \pi (k \in \mathbf {Z}), \\ (n + 1), & \text {当} \alpha = 2 k \pi (k \in \mathbf {Z}), \\ (- 1) ^ {n} (n + 1). & \text {当} \alpha = (2 k + 1) \pi (k \in \mathbf {Z}). \end{array} \right.
$$

##### 例8
例8 设  $a_1, a_2, \dots, a_n$  是数域  $K$  中互不相同的数， $b_1, b_2, \dots, b_n$  是  $K$  中任意一组给定的数。证明：存在唯一的数域  $K$  上的多项式  $f(x) = c_1 + c_2x + \dots + c_nx^{n-1}$  使得

$$
f \left(a _ {i}\right) = b _ {i}, \quad i = 1, 2, \dots , n.
$$

证明 如果多项式  $f(x) = c_{1} + c_{2}x + \dots +c_{n}x^{n - 1}$  使得

$$
f \left(a _ {i}\right) = b _ {i}, \quad i = 1, 2, \dots , n,
$$

那么有关于未知量  $c_{1}, c_{2}, \cdots, c_{n}$  的线性方程组：

$$
\left\{ \begin{array}{l} c _ {1} + c _ {2} a _ {1} + \dots + c _ {n} a _ {1} ^ {n - 1} = b _ {1}, \\ c _ {1} + c _ {2} a _ {2} + \dots + c _ {n} a _ {2} ^ {n - 1} = b _ {2}, \\ \dots \quad \dots \quad \dots \quad \dots \quad \dots \\ c _ {1} + c _ {2} a _ {n} + \dots + c _ {n} a _ {n} ^ {n - 1} = b _ {n}. \end{array} \right.
$$

它的系数行列式与关于  $a_1, a_2, \dots, a_n$  的范德蒙行列式相等。由于  $a_1, a_2, \dots, a_n$  两两不同，因此系数行列式不等于0，从而上述线性方程组有唯一解，于是存在唯一的多项式  $f(x)$  满足要求。

