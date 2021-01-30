PROJNAME=vitae

.PHONY: $(PROJNAME).pdf all clean cleanall cleanrm

all: $(PROJNAME).pdf

$(PROJNAME).pdf: $(PROJNAME).tex
	latexmk -pdf $<

clean: cleanrm
	latexmk -c

cleanall: cleanrm
	latexmk -CA

cleanrm:
	-rm -f bibjcrscopus.{aux,bbl}
	-rm -f bibscielo.{aux,bbl}
	-rm -f bibbookchap.{aux,bbl}
	-rm -f bibreport.{aux,bbl}
	-rm -f bibphdthesis.{aux,bbl}
	-rm -f bibmscthesis.{aux,bbl}
	-rm -f bibubbbscA.{aux,bbl}
	-rm -f bibubbbscB.{aux,bbl}
	-rm -f biboralkey.{aux,bbl}
	-rm -f biboralA.{aux,bbl}
	-rm -f biboralB.{aux,bbl}
