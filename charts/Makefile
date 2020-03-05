DST=../../helm-charts

update-helm-charts: clean
	helm lint --strict chart-updater
	find . -maxdepth 1 -type d -print | while read PKG; do helm package $$PKG; done
	helm repo index --url https://rossumai.github.io/helm-charts/ --merge $(DST)/index.yaml .
	mv index.yaml $(DST)/index.yaml
	cp *.tgz $(DST)
	PKGS=`ls -1 *.tgz`; cd $(DST); git add $$PKGS index.yaml; git commit -m "Release of $$PKGS"

clean:
	rm -f *.tgz index.yaml
