.PHONY: all
all: gen build

.PHONY: gen
gen:
	dagger mod gen

.PHONY: build
build:
	dagger mod build

.PHONY: publish
publish:
	dagger mod publish

.PHONY: clean
clean:
	rm -rf gen/ 