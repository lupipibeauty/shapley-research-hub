\NeedsTeXFormat{LaTeX2e}
\ProvidesClass{coursepaper}[2026/11/08 Course paper template derived from the supplied DOCX]

\LoadClass[UTF8,12pt,fontset=none,letterpaper]{ctexart}

\RequirePackage{fontspec}
\RequirePackage{geometry}
\RequirePackage{fancyhdr}
\RequirePackage{titlesec}
\RequirePackage{tocloft}
\RequirePackage{caption}
\RequirePackage{booktabs}
\RequirePackage{tabularx}
\RequirePackage{array}
\RequirePackage{amsmath}
\RequirePackage{amssymb}
\RequirePackage{setspace}
\RequirePackage{etoolbox}
\RequirePackage{gbt7714}
\RequirePackage{graphicx}
\RequirePackage{xcolor}
\RequirePackage{hyperref}
\renewcommand{\refname}{参考文献}

\geometry{
  letterpaper,
  top=1in,
  bottom=1in,
  left=1.25in,
  right=1.25in,
  headheight=12pt,
  headsep=0.2in,
  footskip=0.45in
}

\setmainfont[
  Path=C:/Windows/Fonts/,
  UprightFont=times.ttf,
  BoldFont=timesbd.ttf,
  ItalicFont=timesi.ttf,
  BoldItalicFont=timesbi.ttf
]{Times New Roman}

\setCJKmainfont[
  Path=C:/Windows/Fonts/,
  UprightFont=simsun.ttc,
  BoldFont=simhei.ttf,
  ItalicFont=simkai.ttf
]{SimSun}
\setCJKsansfont[
  Path=C:/Windows/Fonts/,
  UprightFont=simhei.ttf
]{SimHei}
\setCJKmonofont[
  Path=C:/Windows/Fonts/,
  UprightFont=simfang.ttf
]{FangSong}

\newCJKfontfamily\paperbodyfont[
  Path=C:/Windows/Fonts/,
  UprightFont=simsun.ttc,
  BoldFont=simhei.ttf,
  ItalicFont=simkai.ttf
]{SimSun}
\newCJKfontfamily\paperheiti[
  Path=C:/Windows/Fonts/,
  UprightFont=simhei.ttf
]{SimHei}
\newCJKfontfamily\paperkaiti[
  Path=C:/Windows/Fonts/,
  UprightFont=simkai.ttf,
  BoldFont=simkai.ttf
]{KaiTi}
\newCJKfontfamily\paperzhongsong[
  Path=C:/Windows/Fonts/,
  UprightFont=STZHONGS.TTF,
  BoldFont=STZHONGS.TTF
]{STZhongsong}
\newCJKfontfamily\covertitlefont[
  Path=C:/Windows/Fonts/,
  UprightFont=STKAITI.TTF,
  BoldFont=STKAITI.TTF
]{STKaiti}

\linespread{1.25}
\setlength{\parindent}{2em}
\setlength{\parskip}{0pt}
\setlength{\emergencystretch}{2em}
\setlength{\footskip}{0.45in}

\pagestyle{fancy}
\fancyhf{}
\newcommand{\courseheader}{%
  \paperbodyfont\fontsize{9pt}{12pt}\selectfont
  中南财经政法大学研究生《\coursenamevalue》论文
}
\fancyhead[C]{\courseheader}
\fancyfoot[C]{\thepage}
\renewcommand{\headrulewidth}{0pt}
\renewcommand{\footrulewidth}{0pt}

\fancypagestyle{coursepaperempty}{%
  \fancyhf{}
  \renewcommand{\headrulewidth}{0pt}
  \renewcommand{\footrulewidth}{0pt}
}
\fancypagestyle{plain}{%
  \fancyhf{}
  \fancyhead[C]{\courseheader}
  \fancyfoot[C]{\thepage}
  \renewcommand{\headrulewidth}{0pt}
  \renewcommand{\footrulewidth}{0pt}
}

\titleformat{\section}
  {\paperheiti\bfseries\fontsize{14pt}{18pt}\selectfont}
  {\thesection}{0.8em}{}
\titlespacing*{\section}{0pt}{18pt}{4pt}

\titleformat{\subsection}
  {\paperheiti\bfseries\fontsize{12pt}{16pt}\selectfont}
  {\thesubsection}{0.8em}{}
\titlespacing*{\subsection}{0pt}{8pt}{4pt}

\titleformat{\subsubsection}
  {\paperheiti\bfseries\fontsize{12pt}{16pt}\selectfont}
  {\thesubsubsection}{0.8em}{}
\titlespacing*{\subsubsection}{0pt}{8pt}{4pt}

\titleformat{\paragraph}
  {\paperbodyfont\itshape\fontsize{12pt}{18pt}\selectfont}
  {\theparagraph}{0.8em}{}
\titlespacing*{\paragraph}{0pt}{4pt}{2pt}

\renewcommand{\contentsname}{目\quad 录}
\setcounter{tocdepth}{3}
\renewcommand{\cfttoctitlefont}{
  \paperheiti\bfseries\fontsize{14pt}{18pt}\selectfont
}
\renewcommand{\cftaftertoctitle}{\par\vspace{6pt}}
\renewcommand{\cftsecfont}{\paperbodyfont\fontsize{11pt}{16pt}\selectfont}
\renewcommand{\cftsecpagefont}{\paperbodyfont\fontsize{11pt}{16pt}\selectfont}
\renewcommand{\cftsubsecfont}{\paperbodyfont\fontsize{11pt}{16pt}\selectfont}
\renewcommand{\cftsubsecpagefont}{\paperbodyfont\fontsize{11pt}{16pt}\selectfont}
\renewcommand{\cftsubsubsecfont}{\paperbodyfont\fontsize{11pt}{16pt}\selectfont}
\renewcommand{\cftsubsubsecpagefont}{\paperbodyfont\fontsize{11pt}{16pt}\selectfont}
\setlength{\cftbeforetoctitleskip}{0pt}
\setlength{\cftaftertoctitleskip}{0pt}
\setlength{\cftsecindent}{0pt}
\setlength{\cftsubsecindent}{2em}
\setlength{\cftsubsubsecindent}{4em}
\renewcommand{\cftsecleader}{\cftdotfill{\cftdotsep}}
\renewcommand{\cftsubsecleader}{\cftdotfill{\cftdotsep}}
\renewcommand{\cftsubsubsecleader}{\cftdotfill{\cftdotsep}}

\DeclareCaptionFont{papercaption}{
  \paperbodyfont\fontsize{10.5pt}{15pt}\selectfont
}
\captionsetup{
  font=papercaption,
  labelsep=none,
  justification=centering,
  singlelinecheck=true,
  skip=6pt
}
\captionsetup[table]{position=top,skip=6pt}
\captionsetup[figure]{position=bottom,skip=6pt}
\renewcommand{\thefigure}{\thesection-\arabic{figure}}
\renewcommand{\thetable}{\thesection-\arabic{table}}
\counterwithin{figure}{section}
\counterwithin{table}{section}
\renewcommand{\figurename}{图}
\renewcommand{\tablename}{表}

\renewcommand{\arraystretch}{1.25}
\setlength{\arrayrulewidth}{0.5pt}

\hypersetup{
  hidelinks,
  bookmarksnumbered=true,
  pdfstartview=FitH
}

\newcommand{\coursenamevalue}{深度学习理论与方法}
\newcommand{\papertitlevalue}{基于图神经网络的关系数据贡献估算方法研究}
\newcommand{\studentidvalue}{202511200042}
\newcommand{\studentnamevalue}{陆梦飞}
\newcommand{\classnamevalue}{25学硕一班}
\newcommand{\completiondatevalue}{2026年11月8日}
\newcommand{\documenttypevalue}{课程论文}

\newcommand{\coursename}[1]{\renewcommand{\coursenamevalue}{#1}}
\newcommand{\papertitle}[1]{\renewcommand{\papertitlevalue}{#1}}
\newcommand{\studentid}[1]{\renewcommand{\studentidvalue}{#1}}
\newcommand{\studentname}[1]{\renewcommand{\studentnamevalue}{#1}}
\newcommand{\classname}[1]{\renewcommand{\classnamevalue}{#1}}
\newcommand{\completiondate}[1]{\renewcommand{\completiondatevalue}{#1}}
\newcommand{\documenttype}[1]{\renewcommand{\documenttypevalue}{#1}}

\newcommand{\coverfield}[2]{%
  \paperheiti\bfseries\fontsize{14pt}{18pt}\selectfont
  #1 & \centering\arraybackslash #2 \\[0.45cm]
}

\newcommand{\makecoverpage}{%
  \begin{titlepage}
    \thispagestyle{coursepaperempty}
    \centering
    \vspace*{0.8cm}
    {\paperzhongsong\bfseries\fontsize{24pt}{32pt}\selectfont
      中南财经政法大学研究生\par}
    \vspace{0.18cm}
    {\paperzhongsong\bfseries\fontsize{24pt}{32pt}\selectfont
      《\coursenamevalue》\par}
    \vspace{0.25cm}
    {\covertitlefont\bfseries\fontsize{26pt}{34pt}\selectfont
      \documenttypevalue\par}
    \vspace{0.55cm}
    \includegraphics[width=6.6cm]{assets/logo.png}\par
    \vspace{0.55cm}
    \renewcommand{\arraystretch}{1.0}
    \begin{tabularx}{14.2cm}{@{}>{\raggedright\arraybackslash}p{3.9cm}X@{}}
      \coverfield{研究题目：}{\papertitlevalue}
      \coverfield{完成时间：}{\completiondatevalue}
      \coverfield{学\quad\quad 号：}{\studentidvalue}
      \coverfield{姓\quad\quad 名：}{\studentnamevalue}
      \coverfield{班\quad\quad 级：}{\classnamevalue}
    \end{tabularx}
    \vfill
  \end{titlepage}
}

\newcommand{\maketocpage}{%
  \clearpage
  \pagestyle{coursepaperempty}
  \tableofcontents
  \thispagestyle{coursepaperempty}
  \clearpage
}

\newenvironment{cnabstract}[1]{%
  \clearpage
  \thispagestyle{coursepaperempty}
  \begin{center}
    \paperheiti\bfseries\fontsize{18pt}{27pt}\selectfont
    \papertitlevalue
  \end{center}
  \vspace{0.4cm}
  \begingroup
  \gdef\coursepaperkeywords{#1}
  \paperbodyfont\fontsize{10.5pt}{15.75pt}\selectfont
  \setlength{\parindent}{2em}
  \noindent\textbf{摘\quad 要：}\ignorespaces
}{%
  \par\vspace{0.45cm}
  \noindent\textbf{关键词：}\ignorespaces\coursepaperkeywords
  \par\endgroup
}

\newcommand{\beginmainmatter}{%
  \clearpage
  \setcounter{page}{1}
  \pagestyle{fancy}
}

\newcommand{\referencesection}{%
  \clearpage
  \phantomsection
  \begingroup
  \paperbodyfont\fontsize{10.5pt}{13.125pt}\selectfont
  \setlength{\parindent}{0pt}
  \setlength{\itemsep}{0pt}
  \setlength{\parsep}{0pt}
  \setlength{\parskip}{0pt}
}

\newcommand{\finishreferencesection}{\thispagestyle{fancy}\par\endgroup}

\renewcommand{\bibsection}{%
  \thispagestyle{fancy}%
  \begin{center}
    \paperheiti\bfseries\fontsize{14pt}{18pt}\selectfont
    \refname
  \end{center}
  \addcontentsline{toc}{section}{\refname}%
}
\AtBeginEnvironment{thebibliography}{\thispagestyle{fancy}}

\endinput
