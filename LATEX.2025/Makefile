PROJNAME=vitae

.PHONY: $(PROJNAME).pdf all clean cleanall cleanrm

all: $(PROJNAME).pdf

$(PROJNAME).pdf: $(PROJNAME).tex
	latexmk -pdf $<

PAPER: $(PROJNAME)PAPER.tex
	latexmk $<
	latex2rtf $<
	latexmk -CA $<
	rm $(PROJNAME)PAPER.bbl

clean: cleanrm
	latexmk -c

cleanall: cleanrm
	latexmk -CA

cleanrm:
	-rm -f bibjcr.{aux,bbl}
	-rm -f bibsjr.{aux,bbl}
	-rm -f bibcon.{aux,bbl}
	-rm -f bibart.{aux,bbl}
	-rm -f bibpre.{aux,bbl}
	-rm -f bibphdthesis.{aux,bbl}
	-rm -f bibmscthesis.{aux,bbl}
	-rm -f bibubbbscA.{aux,bbl}
	-rm -f bibubbbscB.{aux,bbl}
	-rm -f biboralkey.{aux,bbl}
	-rm -f biboralA.{aux,bbl}
	-rm -f biboralB.{aux,bbl}
